"""
Negative-Binomial Count Regression + SHAP-lite Attribution (Plan 05 Sec.3.3,
Stage 2).

Statistical model chosen and why
---------------------------------
DEEPTHINK_10 requires a defect-count model that controls for LOC and churn
so a rule's association with defects is measured *incrementally* (a pure
size proxy must not look predictive). Defect counts are non-negative
integers with typical over-dispersion (variance > mean) relative to a
Poisson assumption, so Negative Binomial (NB2) regression is the
appropriate count model.

A full NB requires jointly maximum-likelihood-fitting the mean-model
coefficients *and* the dispersion parameter `alpha`, which needs a 1-D
numerical search nested inside the IRLS loop. That is heavier than
justified for a pure-stdlib, deterministic implementation, so this module
uses the documented, standard simplification: fit `alpha` once via the
method-of-moments over-dispersion estimator
(`alpha = max(0, (Var(y) - Mean(y)) / Mean(y)^2)`), then treat it as a
fixed offset while fitting the mean-model coefficients `beta` by Iteratively
Reweighted Least Squares (IRLS) with a log link, exactly the same convex
optimization GLM libraries use for the beta step. `alpha == 0` degenerates
this into a quasi-Poisson fit, which is the honest fallback for
under-dispersed or too-small samples. This is *not* full NB MLE, and that
boundary is stated up front rather than glossed over.

SHAP-lite attribution
----------------------
For an additive log-link linear predictor `eta = beta_0 + sum_j beta_j *
x_j`, the coalition value function `v(S) = sum_{j in S} beta_j * (x_j -
E[x_j])` is additive across features by construction (no interaction
terms exist to distribute). The Shapley value of feature `j` for *any*
additive `v` is exactly its own marginal contribution, independent of
coalition order:

    phi_j = beta_j * (x_j - E[x_j])

No permutation sampling is required - this is an exact closed form for
this model class, not an approximation of it. It is only "lite" relative
to SHAP for a nonlinear/interacting model (e.g. a tree ensemble), where
exact Shapley is intractable and TreeSHAP-style algorithms are needed
instead. Documented here as the plan's "linearized attribution" option.

All arithmetic is pure `math`/stdlib - no numpy/scipy dependency.
"""

import math
from typing import Dict, List, NamedTuple, Sequence

from Asgard.Bragi.Calibration.models.calibration_models import FeatureAttribution, NBModelFit

_MAX_ITER = 50
_TOLERANCE = 1e-6
_ETA_CLIP = 20.0
_MIN_MU = 1e-6
_RIDGE = 1e-8  # tiny ridge term so (X'WX) stays invertible under collinearity


class Observation(NamedTuple):
    """One file's feature vector + observed defect count for the NB fit."""
    file_path: str
    features: Dict[str, float]  # feature_name -> value (must cover every name in `fit`)
    defect_count: int


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def _moment_alpha(y: Sequence[float]) -> float:
    """Method-of-moments NB2 dispersion estimator, clamped to >= 0."""
    m = _mean(y)
    if m <= 0:
        return 0.0
    v = _variance(y)
    alpha = (v - m) / (m * m)
    return max(alpha, 0.0)


def _solve_linear_system(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting; `a` is square, small (p x p)."""
    n = len(a)
    # Augment
    aug = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-15:
            continue  # singular column - leave as-is, resulting coefficient will be ~0
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= pivot
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                aug[r][j] -= factor * aug[col][j]
    return [aug[i][n] for i in range(n)]


def fit_negative_binomial(
    observations: List[Observation], feature_names: Sequence[str]
) -> NBModelFit:
    """
    Fit `mu = exp(intercept + sum beta_j * x_j)` via IRLS under a fixed,
    method-of-moments NB2 dispersion `alpha`. Deterministic: zero-vector
    coefficient seed, fixed iteration cap, no randomness anywhere.
    """
    feature_names = list(feature_names)
    n = len(observations)
    p = len(feature_names) + 1  # + intercept
    if n < p + 1:
        return NBModelFit(feature_names=feature_names, coefficients={}, converged=False, n=n)

    x = [[1.0] + [float(o.features.get(f, 0.0)) for f in feature_names] for o in observations]
    y = [float(o.defect_count) for o in observations]
    alpha = _moment_alpha(y)

    beta = [0.0] * p
    # Warm-start intercept at log(mean(y)) so the first iteration's mu is sane.
    mean_y = _mean(y)
    beta[0] = math.log(mean_y) if mean_y > 0 else 0.0

    converged = False
    iterations = 0
    for iterations in range(1, _MAX_ITER + 1):
        eta = [sum(x[i][j] * beta[j] for j in range(p)) for i in range(n)]
        eta = [max(-_ETA_CLIP, min(_ETA_CLIP, e)) for e in eta]
        mu = [max(math.exp(e), _MIN_MU) for e in eta]

        weights = [m / (1.0 + alpha * m) for m in mu]
        z = [eta[i] + (y[i] - mu[i]) / mu[i] for i in range(n)]

        xtwx = [[0.0] * p for _ in range(p)]
        xtwz = [0.0] * p
        for i in range(n):
            w = weights[i]
            xi = x[i]
            for a_ in range(p):
                xtwz[a_] += w * xi[a_] * z[i]
                for b_ in range(p):
                    xtwx[a_][b_] += w * xi[a_] * xi[b_]
        for a_ in range(p):
            xtwx[a_][a_] += _RIDGE

        beta_new = _solve_linear_system(xtwx, xtwz)
        delta = max(abs(beta_new[k] - beta[k]) for k in range(p))
        beta = beta_new
        if delta < _TOLERANCE:
            converged = True
            break

    coefficients = {"intercept": beta[0]}
    for idx, name in enumerate(feature_names):
        coefficients[name] = beta[idx + 1]

    return NBModelFit(
        feature_names=feature_names,
        coefficients=coefficients,
        alpha=alpha,
        converged=converged,
        n=n,
        iterations=iterations,
    )


def feature_attribution(
    fit: NBModelFit,
    observations: List[Observation],
    rule_feature: str,
    control_features: Sequence[str],
) -> FeatureAttribution:
    """
    Exact Shapley/linearized attribution (see module docstring) for
    `rule_feature` vs the summed `control_features` (LOC + churn), averaged
    over `observations` in absolute value - the incremental-signal
    comparison DEEPTHINK_10 requires: a rule only "counts" if its own
    attribution is not dwarfed by the size/activity controls.
    """
    if not fit.coefficients or not observations:
        return FeatureAttribution(rule_id="")

    baseline = {
        name: _mean([o.features.get(name, 0.0) for o in observations])
        for name in fit.feature_names
    }

    rule_attrs: List[float] = []
    control_attrs: List[float] = []
    per_feature_sums: Dict[str, float] = {name: 0.0 for name in fit.feature_names}

    for obs in observations:
        for name in fit.feature_names:
            beta_j = fit.coefficients.get(name, 0.0)
            x_j = obs.features.get(name, 0.0)
            contribution = beta_j * (x_j - baseline[name])
            per_feature_sums[name] += contribution
            if name == rule_feature:
                rule_attrs.append(abs(contribution))
        control_total = sum(
            fit.coefficients.get(name, 0.0) * (obs.features.get(name, 0.0) - baseline[name])
            for name in control_features
        )
        control_attrs.append(abs(control_total))

    n = len(observations)
    return FeatureAttribution(
        rule_id="",
        mean_abs_rule_attribution=_mean(rule_attrs),
        mean_abs_control_attribution=_mean(control_attrs),
        per_feature_mean_attribution={k: v / n for k, v in per_feature_sums.items()},
    )
