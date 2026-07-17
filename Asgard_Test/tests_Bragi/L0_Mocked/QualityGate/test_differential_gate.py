"""
Tests for the fingerprint-based differential gate (Plan Heimdall-09 §§1-5,
Bragi-06 §3.2): blocking policy, suppression governance, zero-flakiness
demotion, break-glass, and epistemic honesty on missing baselines.
"""

from datetime import date

import pytest

from Asgard.Bragi.QualityGate.baseline_store import (
    BranchBaseline,
    FingerprintBaselineStore,
)
from Asgard.Bragi.QualityGate.fingerprint import compute_fingerprint
from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    BreakGlassRecord,
    GateFinding,
    GateStatus,
)
from Asgard.Bragi.QualityGate.services._differential_engine import (
    DifferentialGateEngine,
    coerce_finding,
    verify_scan_determinism,
)
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import (
    QualityGateEvaluator,
)
from Asgard.Bragi.QualityGate.suppressions import parse_suppressions

TODAY = date(2026, 7, 17)


def finding(rule="SQLI", path="src/app.py", line=3, severity="critical",
            confidence=0.9, snippet="db.execute(q)"):
    return GateFinding(
        rule_id=rule, file_path=path, line=line, severity=severity,
        confidence=confidence, snippet=snippet,
    )


def baseline_of(*findings_):
    fps = [
        compute_fingerprint(f.rule_id, f.file_path, snippet=f.snippet or None)
        for f in findings_
    ]
    return BranchBaseline(branch="main", commit="base123", fingerprints=fps)


class TestBlockingPolicy:
    def test_new_critical_fails(self):
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([finding(severity="critical")], baseline_of())
        assert result.status == GateStatus.FAILED or result.status == "failed"
        assert len(result.blocking_findings) == 1

    def test_new_high_fails(self):
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([finding(severity="high")], baseline_of())
        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_new_medium_does_not_block(self):
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([finding(severity="medium")], baseline_of())
        assert result.status == GateStatus.WARNING or result.status == "warning"
        assert result.blocking_findings == []
        assert len(result.advisory_findings) == 1

    def test_preexisting_critical_passes(self):
        """Legacy findings never hold unrelated work hostage."""
        legacy = finding(severity="critical")
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([legacy], baseline_of(legacy))
        assert result.status == GateStatus.PASSED or result.status == "passed"
        assert result.preexisting_count == 1
        assert result.new_findings == []

    def test_low_confidence_never_blocks(self):
        """Possible/Unlikely (<0.50) findings can never block."""
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate(
            [finding(severity="critical", confidence=0.3)], baseline_of()
        )
        assert result.blocking_findings == []
        assert result.status == GateStatus.WARNING or result.status == "warning"

    def test_debt_substitution_still_fails(self):
        """Introducing a CRITICAL while 'fixing' an unrelated LOW must FAIL
        (proves count ratchets are abandoned)."""
        old_low = finding(rule="NAMING", severity="low", snippet="badName")
        new_critical = finding(rule="SQLI", severity="critical")
        # Baseline contains the low finding; head scan fixed it but added a critical.
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([new_critical], baseline_of(old_low))
        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_line_shift_is_not_new(self):
        """A refactor shifting an existing finding's lines is not a new finding."""
        src_before = (
            "def handler(request):\n"
            "    q = 'SELECT ' + request.args['id']\n"
            "    return db.execute(q)\n"
        )
        src_after = "# comment\n# comment\n\n" + src_before
        base_fp = compute_fingerprint("SQLI", "src/app.py", source=src_before, line=2)
        baseline = BranchBaseline(branch="main", commit="c", fingerprints=[base_fp])

        shifted = GateFinding(
            rule_id="SQLI", file_path="src/app.py", line=5, severity="critical"
        )
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate(
            [shifted], baseline, sources={"src/app.py": src_after}
        )
        assert result.new_findings == []
        assert result.preexisting_count == 1
        assert result.status == GateStatus.PASSED or result.status == "passed"


class TestEpistemicHonesty:
    def test_no_baseline_is_not_evaluated_never_passed(self):
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([finding()], None)
        assert result.status == GateStatus.NOT_EVALUATED or result.status == "not_evaluated"
        assert result.baseline_available is False
        assert "NOT EVALUATED" in result.summary

    def test_clean_diff_passes(self):
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([], baseline_of())
        assert result.status == GateStatus.PASSED or result.status == "passed"


class TestSuppressionGovernance:
    def test_valid_fp_suppression_silences_finding(self):
        directives = parse_suppressions(
            "# heimdall-ignore: SQLI - FP: id cast to int\n",
            file_path="src/app.py",
        )
        directives[0].line = 3
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate(
            [finding()], baseline_of(), suppressions=directives
        )
        assert result.blocking_findings == []
        assert len(result.suppressed_findings) == 1
        assert result.status != GateStatus.FAILED and result.status != "failed"

    def test_bare_suppression_fails_gate(self):
        directives = parse_suppressions(
            "# heimdall-ignore: SQLI\n", file_path="src/app.py"
        )
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([], baseline_of(), suppressions=directives)
        assert result.status == GateStatus.FAILED or result.status == "failed"
        assert len(result.suppression_violations) == 1

    def test_expired_risk_accepted_fails_gate(self):
        directives = parse_suppressions(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2020-01-01 - T-1\n",
            file_path="src/app.py",
        )
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([finding()], baseline_of(), suppressions=directives)
        # Expired directive is a violation AND no longer silences the finding.
        assert result.status == GateStatus.FAILED or result.status == "failed"
        assert len(result.suppression_violations) == 1
        assert len(result.blocking_findings) == 1


class TestZeroFlakiness:
    def test_flaky_rule_demoted_to_warn_only(self):
        engine = DifferentialGateEngine(flaky_rules={"SQLI"}, today=TODAY)
        result = engine.evaluate([finding(severity="critical")], baseline_of())
        assert result.blocking_findings == []
        assert result.demoted_flaky_rules == ["SQLI"]
        assert result.status == GateStatus.WARNING or result.status == "warning"

    def test_verify_scan_determinism_flags_flaky_rules(self):
        stable = finding(rule="STABLE", snippet="x")
        flaky_a = finding(rule="FLAKY", snippet="a")
        flaky_b = finding(rule="FLAKY", snippet="b")
        for f in (stable, flaky_a, flaky_b):
            f.fingerprint = compute_fingerprint(
                f.rule_id, f.file_path, snippet=f.snippet
            )
        assert verify_scan_determinism(
            [stable, flaky_a], [stable, flaky_b]
        ) == ["FLAKY"]

    def test_verify_scan_determinism_clean(self):
        f = finding()
        f.fingerprint = "fp"
        assert verify_scan_determinism([f], [f]) == []


class TestBreakGlass:
    def test_break_glass_bypasses_but_is_audited(self):
        record = BreakGlassRecord(actor="oncall@example.com", reason="prod down")
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate(
            [finding(severity="critical")], baseline_of(), break_glass=record
        )
        # Bypass never yields an honest PASS - it degrades to WARNING.
        assert result.status == GateStatus.WARNING or result.status == "warning"
        assert result.break_glass is not None
        assert result.break_glass.actor == "oncall@example.com"
        assert len(result.break_glass.bypassed_findings) == 1
        assert "BREAK-GLASS" in result.summary

    def test_break_glass_unused_when_nothing_blocks(self):
        record = BreakGlassRecord(actor="dev", reason="unnecessary")
        engine = DifferentialGateEngine(today=TODAY)
        result = engine.evaluate([], baseline_of(), break_glass=record)
        assert result.break_glass is None
        assert result.status == GateStatus.PASSED or result.status == "passed"


class TestCoercion:
    def test_coerce_from_dict(self):
        f = coerce_finding({
            "rule": "XSS", "file": "a.js", "line_number": "7",
            "severity": "HIGH", "confidence": "0.8", "message": "m",
        })
        assert f.rule_id == "XSS"
        assert f.file_path == "a.js"
        assert f.line == 7
        assert f.severity == "high"
        assert f.confidence == pytest.approx(0.8)

    def test_coerce_from_object(self):
        class Violation:
            violation_type = "lazy_import"
            file_path = "src/x.py"
            line_number = 12
            message = "import inside function"

        f = coerce_finding(Violation())
        assert f.rule_id == "lazy_import"
        assert f.line == 12
        assert f.severity == "medium"

    def test_unknown_severity_defaults_medium(self):
        f = coerce_finding({"rule_id": "R", "file_path": "f", "severity": "bananas"})
        assert f.severity == "medium"


class TestEvaluatorIntegration:
    def test_evaluate_differential_via_store(self, tmp_path):
        legacy = finding(rule="OLD", severity="critical", snippet="legacy()")
        store = FingerprintBaselineStore(tmp_path)
        store.capture("main", "sha1", [
            compute_fingerprint(legacy.rule_id, legacy.file_path,
                                snippet=legacy.snippet),
        ])

        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate_differential(
            [legacy, finding(rule="NEW", severity="high", snippet="oops()")],
            project_path=tmp_path,
            base_branch="main",
        )
        assert result.status == GateStatus.FAILED or result.status == "failed"
        assert result.preexisting_count == 1
        assert len(result.blocking_findings) == 1
        assert result.baseline_commit == "sha1"

    def test_evaluate_differential_missing_baseline_not_evaluated(self, tmp_path):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate_differential(
            [finding()], project_path=tmp_path, base_branch="main"
        )
        assert result.status == GateStatus.NOT_EVALUATED or result.status == "not_evaluated"

    def test_pr_evaluation_never_writes_baseline(self, tmp_path):
        """Cache discipline: PR evaluations are read-only on the store."""
        store = FingerprintBaselineStore(tmp_path)
        store.capture("main", "sha1", ["fp1"])
        before = store.store_path.read_bytes()

        evaluator = QualityGateEvaluator()
        evaluator.evaluate_differential(
            [finding()], project_path=tmp_path, base_branch="main"
        )
        assert store.store_path.read_bytes() == before
