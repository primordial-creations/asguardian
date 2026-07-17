"""
Volundr Composite Scoring Tests (plan 07).

Adversarial tests per DEEPTHINK_01 §1 / DEEPTHINK_05 §1: dilution,
sea-of-lows, veto, verbosity, environment profiles, suppression receipts,
determinism, and the monotonicity property (adding a finding never
increases any dimension score).
"""

from datetime import date, timedelta

import pytest

from Asgard.Volundr.Validation import (
    ScoreDimension,
    ScoreReport,
    ScoringEngine,
    Suppression,
    SuppressionEngine,
    SuppressionSet,
    compute_posture_index,
    letter_grade,
    profile_weights,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)


def finding(rule_id, target, category=ValidationCategory.SECURITY,
            severity=ValidationSeverity.ERROR, message=None):
    return ValidationResult(
        rule_id=rule_id,
        message=message or f"{rule_id} on {target}",
        severity=severity,
        category=category,
        resource_name=target,
        context={"target": target},
    )


def critical_security(target="web"):
    # VOL-K8S-0009 (privileged) is CRITICAL in the registry.
    return finding("VOL-K8S-0009", target)


def high_security(target="web"):
    # VOL-K8S-0001 (runAsNonRoot) is HIGH in the registry.
    return finding("VOL-K8S-0001", target)


def low_maintainability(target="web", n=0):
    # "missing-labels" is LOW / best-practice in the registry.
    return finding(
        "missing-labels", target,
        category=ValidationCategory.BEST_PRACTICE,
        severity=ValidationSeverity.INFO,
        message=f"low finding {n} on {target}",
    )


class TestSecurityVeto:
    def test_critical_caps_composite_at_50(self):
        report = ScoringEngine().score([critical_security()], resources=["web"])
        assert report.composite <= 50
        assert report.veto_applied == "critical"

    def test_high_caps_composite_at_70(self):
        report = ScoringEngine().score([high_security()], resources=["web"])
        assert report.composite <= 70
        assert report.veto_applied == "high"

    def test_clean_artifact_scores_100(self):
        report = ScoringEngine().score([], resources=["web", "svc"])
        assert report.composite == 100.0
        assert report.grade == "A"
        assert report.veto_applied is None

    def test_veto_holds_regardless_of_other_dimensions(self):
        # A perfect artifact in all other dimensions + 1 privileged
        # container must still be <= 50 (DEEPTHINK_05 §3).
        many_resources = [f"cm-{i}" for i in range(40)] + ["web"]
        report = ScoringEngine().score(
            [critical_security("web")], resources=many_resources
        )
        assert report.composite <= 50


class TestAntiGaming:
    def test_dilution_does_not_lift_composite(self):
        """Adding 50 trivially-secure ConfigMaps must not raise the score."""
        engine = ScoringEngine()
        base = engine.score([critical_security("web")], resources=["web"])
        diluted = engine.score(
            [critical_security("web")],
            resources=["web"] + [f"trivial-cm-{i}" for i in range(50)],
        )
        assert diluted.composite <= base.composite + 0.01

    def test_sea_of_lows_cannot_beat_the_veto(self):
        """Fixing 20 LOWs while 1 CRITICAL remains stays <= veto cap."""
        engine = ScoringEngine()
        lows = [low_maintainability("web", n=i) for i in range(20)]
        before = engine.score([critical_security("web")] + lows, resources=["web"])
        after = engine.score([critical_security("web")], resources=["web"])
        assert before.composite <= 50
        assert after.composite <= 50

    def test_verbosity_never_raises_maintainability(self):
        """Extra redundant-declaration findings can only lower the score."""
        engine = ScoringEngine()
        clean = engine.score([], resources=["web"])
        verbose = engine.score(
            [low_maintainability("web"),
             finding("variable-no-description", "web",
                     category=ValidationCategory.BEST_PRACTICE,
                     severity=ValidationSeverity.INFO)],
            resources=["web"],
        )
        get = lambda r: r.dimension(ScoreDimension.MAINTAINABILITY).score  # noqa: E731
        assert get(verbose) <= get(clean)

    def test_monotonicity_added_finding_never_increases_any_dimension(self):
        """Property: every added finding is non-increasing per dimension."""
        engine = ScoringEngine()
        pool = [
            critical_security("web"),
            high_security("api"),
            finding("VOL-K8S-0006", "web",
                    category=ValidationCategory.RELIABILITY,
                    severity=ValidationSeverity.WARNING),
            low_maintainability("api"),
            finding("VOL-K8S-0011", "web",
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.ERROR),
        ]
        resources = ["web", "api"]
        prev = engine.score([], resources=resources)
        current = []
        for f in pool:
            current.append(f)
            report = engine.score(list(current), resources=resources)
            for dim in ScoreDimension:
                assert report.dimension(dim).score <= prev.dimension(dim).score + 1e-9
            assert report.composite <= prev.composite + 1e-9
            prev = report


class TestEnvironmentProfiles:
    def test_profiles_change_weights_not_rule_outcomes(self):
        """Same findings -> identical dimension sub-scores, different composite."""
        engine = ScoringEngine()
        findings = [finding(
            "VOL-K8S-0006", "web",
            category=ValidationCategory.RELIABILITY,
            severity=ValidationSeverity.WARNING,
        )]
        prod = engine.score(findings, resources=["web"], environment="production")
        sandbox = engine.score(findings, resources=["web"], environment="sandbox")
        for dim in ScoreDimension:
            assert prod.dimension(dim).score == sandbox.dimension(dim).score
        # Operability is weighted much lower in sandbox, so the
        # operability gap hurts the sandbox composite less.
        assert sandbox.composite > prod.composite

    def test_unknown_profile_falls_back_to_production(self):
        assert profile_weights("nonsense") == profile_weights("production")


class TestSuppressions:
    def test_suppressed_critical_lifts_veto_and_leaves_receipt(self):
        suppression = Suppression(
            rule="VOL-K8S-0009", target="web", reason="JIRA-123 sandboxed CI runner",
        )
        outcome = SuppressionEngine(
            SuppressionSet(suppressions=[suppression])
        ).apply([critical_security("web")])
        report = ScoringEngine().score(
            outcome.results, resources=["web"], suppressed=outcome.applied,
        )
        assert report.veto_applied is None
        assert report.composite == 100.0
        assert report.suppressed_count == 1
        assert report.suppressed_receipts[0].rule_id == "VOL-K8S-0009"
        assert "JIRA-123" in report.suppressed_receipts[0].reason

    def test_expired_suppression_does_not_lift_veto(self):
        suppression = Suppression(
            rule="VOL-K8S-0009", target="web", reason="expired",
            expires=date.today() - timedelta(days=1),
        )
        outcome = SuppressionEngine(
            SuppressionSet(suppressions=[suppression])
        ).apply([critical_security("web")])
        report = ScoringEngine().score(
            outcome.all_results, resources=["web"], suppressed=outcome.applied,
        )
        assert report.veto_applied == "critical"


class TestDeterminismAndReporting:
    def test_same_findings_same_report(self):
        engine = ScoringEngine()
        findings = [critical_security("web"), low_maintainability("api")]
        a = engine.score(list(findings), resources=["web", "api"])
        b = engine.score(list(reversed(findings)), resources=["api", "web"])
        assert a.composite == b.composite
        assert [d.score for d in a.dimensions] == [d.score for d in b.dimensions]
        assert [r.resource for r in a.resource_scores] == [
            r.resource for r in b.resource_scores
        ]

    def test_letter_grades(self):
        assert letter_grade(95) == "A"
        assert letter_grade(85) == "B"
        assert letter_grade(70) == "C"
        assert letter_grade(55) == "D"
        assert letter_grade(20) == "F"

    def test_remediation_hints_present_and_ranked(self):
        report = ScoringEngine().score(
            [low_maintainability("web"), critical_security("web")],
            resources=["web"],
        )
        assert report.remediation
        assert report.remediation[0].rule_id == "VOL-K8S-0009"
        assert report.remediation[0].severity == "critical"

    def test_delta_mode(self):
        engine = ScoringEngine()
        baseline = engine.score([], resources=["web"])
        regressed = engine.score([critical_security("web")], resources=["web"])
        delta = regressed.delta(baseline)
        assert delta["composite"] < 0
        assert delta["security"] < 0

    def test_report_serializes_round_trip(self):
        report = ScoringEngine().score([critical_security("web")], resources=["web"])
        restored = ScoreReport.model_validate_json(report.model_dump_json())
        assert restored.composite == report.composite


class TestPostureIndex:
    def test_weakest_link_dominates(self):
        clean = {f"r{i}": [] for i in range(10)}
        clean_posture = compute_posture_index(clean)
        one_bad = dict(clean)
        one_bad["r0"] = [critical_security("r0")]
        bad_posture = compute_posture_index(one_bad)
        assert bad_posture.posture < clean_posture.posture

    def test_epistemic_floor_never_reports_perfection(self):
        posture = compute_posture_index({"web": []})
        assert posture.posture < 100.0
        assert posture.epistemic_floor == pytest.approx(0.4)

    def test_external_tools_buy_down_uncertainty(self):
        static_only = compute_posture_index({"web": []})
        with_tools = compute_posture_index({"web": []}, external_tools_ran=True)
        assert with_tools.posture > static_only.posture

    def test_assumptions_documented(self):
        posture = compute_posture_index({"web": []})
        assert len(posture.assumptions) == 3

    def test_dilution_defense_zero_edge_resources(self):
        """Padding a graph with disconnected clean resources must not
        materially improve posture (DEEPTHINK_01 §1B)."""
        edges = [("svc", "web")]
        base = compute_posture_index(
            {"web": [critical_security("web")], "svc": []}, edges=edges,
        )
        padded_findings = {"web": [critical_security("web")], "svc": []}
        for i in range(50):
            padded_findings[f"pad-{i}"] = []
        padded = compute_posture_index(padded_findings, edges=edges)
        assert padded.posture <= base.posture + 1.0
