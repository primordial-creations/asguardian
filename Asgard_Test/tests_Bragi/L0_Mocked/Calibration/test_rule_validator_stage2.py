"""
Tests for Plan 05 Stage 2: full-SZZ + NB-regression rule validity
(`rule_validator.compute_rule_validity_stage2` / `combine_stage1_stage2`).

Uses the NB/SHAP-lite machinery directly against synthetic, hand-built
observations (bypassing the git subprocess layer, which `test_szz.py`
already covers end to end) so these tests are fast and deterministic while
still exercising the real statistical pipeline.
"""

import random

from Asgard.Bragi.Calibration.models.calibration_models import (
    SZZResult,
    SZZStatus,
    ValidityReport,
    ValidityVerdict,
)
from Asgard.Bragi.Calibration.services import nb_model, rule_validator


def _fit_and_classify(observations, min_observations=20):
    """
    Exercise the same fit -> attribution -> verdict logic
    `compute_rule_validity_stage2` uses, without going through git/SZZ.
    """
    fit = nb_model.fit_negative_binomial(
        observations, feature_names=list(rule_validator._STAGE2_FEATURES)
    )
    assert fit.converged
    attribution = nb_model.feature_attribution(
        fit, observations, rule_feature=rule_validator._RULE_FEATURE,
        control_features=list(rule_validator._CONTROL_FEATURES),
    )
    beta_rule = fit.coefficients.get(rule_validator._RULE_FEATURE, 0.0)
    control_floor = max(attribution.mean_abs_control_attribution, 1e-9)
    ratio = attribution.mean_abs_rule_attribution / control_floor
    if beta_rule > 0 and ratio >= rule_validator.STAGE2_INCREMENTAL_RATIO:
        return ValidityVerdict.PREDICTIVE, beta_rule, ratio
    if beta_rule < 0 and ratio >= rule_validator.STAGE2_INCREMENTAL_RATIO:
        return ValidityVerdict.NOISY, beta_rule, ratio
    return ValidityVerdict.NEUTRAL, beta_rule, ratio


class TestSyntheticPredictiveRule:
    """A rule perfectly correlated with injected defects -> PREDICTIVE."""

    def test_rule_firing_perfectly_correlated_with_defects(self):
        rng = random.Random(1)
        obs = []
        for i in range(120):
            loc = rng.choice([100, 500, 2000])  # varies independently of the rule
            churn = rng.choice([0, 3, 8])
            firing = rng.choice([0, 1, 2, 3])
            # Defects driven almost entirely by firing; tiny +/-1 noise avoids
            # the perfect-separation non-convergence pathology of MLE count
            # models (a real, documented IRLS behavior, not a test artifact).
            defects = max(0, firing * 2 + rng.choice([-1, 0, 0, 1]))
            obs.append(
                nb_model.Observation(
                    file_path=f"f{i}.py",
                    features={"rule_firing": firing, "loc": loc, "churn": churn},
                    defect_count=defects,
                )
            )
        verdict, beta_rule, ratio = _fit_and_classify(obs)
        assert verdict == ValidityVerdict.PREDICTIVE
        assert beta_rule > 0
        assert ratio >= rule_validator.STAGE2_INCREMENTAL_RATIO


class TestSyntheticSizeProxyRule:
    """A rule that only fires proportionally to LOC -> NEUTRAL, never PREDICTIVE."""

    def test_pure_loc_proxy_rule_scores_neutral(self):
        rng = random.Random(2)
        obs = []
        for i in range(150):
            loc = rng.choice([100, 400, 900, 1600])
            churn = rng.choice([0, 1, 2, 3, 4])
            # The rule fires purely as a function of LOC (a size proxy) - it
            # carries zero information beyond what LOC already tells the model.
            firing = loc // 200
            # Defects genuinely driven by LOC and churn, NOT by the rule
            # beyond what LOC already explains - a size-and-churn-driven
            # ground truth with a collinear size-proxy rule added on top.
            lam = 0.002 * loc + 0.3 * churn
            defects = min(15, int(lam) + rng.choice([0, 0, 1]))
            obs.append(
                nb_model.Observation(
                    file_path=f"f{i}.py",
                    features={"rule_firing": firing, "loc": loc, "churn": churn},
                    defect_count=defects,
                )
            )
        verdict, beta_rule, ratio = _fit_and_classify(obs)
        assert verdict == ValidityVerdict.NEUTRAL
        assert ratio < rule_validator.STAGE2_INCREMENTAL_RATIO


class TestComputeRuleValidityStage2Gates:
    def test_insufficient_data_when_szz_unavailable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            rule_validator.szz,
            "compute_szz",
            lambda repo_root, min_fix_commits=5: SZZResult(
                status=SZZStatus.INSUFFICIENT_DATA, fix_commit_count=2, min_fix_commits=5,
                note="only 2 bug-fix commit(s) identified",
            ),
        )
        report = rule_validator.compute_rule_validity_stage2(
            tmp_path, "R1", file_metrics=[]
        )
        assert report.verdict == ValidityVerdict.INSUFFICIENT_DATA
        assert "SZZ trace unavailable" in report.note

    def test_insufficient_data_when_too_few_observations(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            rule_validator.szz,
            "compute_szz",
            lambda repo_root, min_fix_commits=5: SZZResult(
                status=SZZStatus.OK, fix_commit_count=20, min_fix_commits=5,
                induced_commit_counts={"a.py": 1},
            ),
        )
        report = rule_validator.compute_rule_validity_stage2(
            tmp_path, "R1",
            file_metrics=[rule_validator.RuleFileMetrics("a.py", 1, 100, 1)],
            min_observations=20,
        )
        assert report.verdict == ValidityVerdict.INSUFFICIENT_DATA
        assert report.n == 1


class TestCombineStage1Stage2:
    def test_stage2_overrides_when_available(self):
        stage1 = ValidityReport(
            rule_id="R1", lift=1.5, n=20, verdict=ValidityVerdict.PREDICTIVE, note="stage1"
        )
        stage2 = rule_validator.Stage2ValidityReport(
            rule_id="R1", verdict=ValidityVerdict.NEUTRAL, n=50, fix_commit_count=200, note="stage2"
        )
        combined = rule_validator.combine_stage1_stage2(stage1, stage2)
        assert combined.verdict == ValidityVerdict.NEUTRAL
        assert combined.stage2.note == "stage2"

    def test_stage1_stands_alone_when_stage2_insufficient(self):
        stage1 = ValidityReport(
            rule_id="R1", lift=1.5, n=20, verdict=ValidityVerdict.PREDICTIVE, note="stage1"
        )
        stage2 = rule_validator.Stage2ValidityReport(
            rule_id="R1", verdict=ValidityVerdict.INSUFFICIENT_DATA, note="too few fixes"
        )
        combined = rule_validator.combine_stage1_stage2(stage1, stage2)
        assert combined.verdict == ValidityVerdict.PREDICTIVE
        assert combined.stage2.verdict == ValidityVerdict.INSUFFICIENT_DATA
