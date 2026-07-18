"""
Tests for the Plan 05 Stage-2 Negative-Binomial count model + SHAP-lite
attribution (pure-Python IRLS, no numpy).
"""

import random

from Asgard.Bragi.Calibration.services.nb_model import (
    Observation,
    feature_attribution,
    fit_negative_binomial,
)

FEATURES = ["rule_firing", "loc", "churn"]


def _obs(file_path, rule_firing, loc, churn, defect_count):
    return Observation(
        file_path=file_path,
        features={"rule_firing": rule_firing, "loc": loc, "churn": churn},
        defect_count=defect_count,
    )


class TestFitConvergesOnStrongSignal:
    def test_converges_and_recovers_positive_rule_effect(self):
        rng = random.Random(7)
        obs = []
        for i in range(200):
            loc = rng.choice([100, 300, 600])
            churn = rng.choice([0, 2, 5])
            firing = rng.choice([0, 1, 2, 3])
            # Defect count strongly driven by firing, weak baseline from loc/churn.
            lam = 0.2 + 1.5 * firing + 0.001 * loc + 0.05 * churn
            defects = rng.choice([0, 0, 1]) if lam < 1 else min(10, int(lam))
            obs.append(_obs(f"f{i}.py", firing, loc, churn, defects))

        fit = fit_negative_binomial(obs, FEATURES)
        assert fit.converged
        assert fit.n == 200
        assert fit.coefficients["rule_firing"] > 0

    def test_insufficient_rows_does_not_converge(self):
        obs = [_obs("a.py", 1, 100, 1, 1), _obs("b.py", 0, 100, 0, 0)]
        fit = fit_negative_binomial(obs, FEATURES)
        assert not fit.converged
        assert fit.n == 2


class TestFeatureAttribution:
    def test_zero_variance_feature_has_zero_attribution(self):
        # loc is constant across all rows -> its attribution must be ~0
        # (x_j - baseline_j == 0 for every row), regardless of its coefficient.
        rng = random.Random(3)
        obs = []
        for i in range(60):
            firing = rng.choice([0, 1, 2, 3, 4])
            defects = firing + rng.choice([0, 1])
            obs.append(_obs(f"f{i}.py", firing, 500, 1, defects))

        fit = fit_negative_binomial(obs, FEATURES)
        assert fit.converged
        attribution = feature_attribution(fit, obs, "rule_firing", ["loc", "churn"])
        assert abs(attribution.per_feature_mean_attribution.get("loc", 0.0)) < 1e-9

    def test_dominant_rule_feature_outweighs_constant_controls(self):
        rng = random.Random(11)
        obs = []
        for i in range(80):
            firing = rng.choice([0, 1, 2, 3, 4, 5])
            defects = firing + rng.choice([0, 1])  # slight noise avoids a degenerate perfect fit
            obs.append(_obs(f"f{i}.py", firing, 200, 1, defects))
        fit = fit_negative_binomial(obs, FEATURES)
        assert fit.converged
        attribution = feature_attribution(fit, obs, "rule_firing", ["loc", "churn"])
        assert attribution.mean_abs_rule_attribution > attribution.mean_abs_control_attribution
