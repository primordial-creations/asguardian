"""
PCA Weight Derivation (Plan 05 Phase D / Plan 01 Sec.2's deferred upgrade).

Pure-Python (no numpy dependency) principal-component derivation of
intra-category metric weights: collapses collinear utilities (e.g. WMC and
CBO tend to co-vary) into a first-principal-component loading vector,
normalized to sum to 1 so it drops directly into
`CompositeScoreEngine`'s weight slots.

Deterministic by construction:
    - Fixed power-iteration seed vector (all-ones), fixed iteration count.
    - Sign convention: the component is flipped so its largest-magnitude
      loading is positive (otherwise power iteration's arbitrary sign
      would make output byte-unstable across equivalent runs).
    - Stable input ordering: callers pass an explicit `metric_ids` list;
      output preserves that order.
"""

import math
from typing import Dict, List, Sequence

_ITERATIONS = 200
_EPSILON = 1e-12


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _covariance_matrix(matrix: List[List[float]]) -> List[List[float]]:
    """Sample covariance matrix over columns of `matrix` (rows = observations)."""
    n_obs = len(matrix)
    n_metrics = len(matrix[0]) if matrix else 0
    if n_obs < 2 or n_metrics == 0:
        return [[1.0 if i == j else 0.0 for j in range(n_metrics)] for i in range(n_metrics)]

    means = [_mean([row[j] for row in matrix]) for j in range(n_metrics)]
    cov = [[0.0] * n_metrics for _ in range(n_metrics)]
    for i in range(n_metrics):
        for j in range(n_metrics):
            s = sum((row[i] - means[i]) * (row[j] - means[j]) for row in matrix)
            cov[i][j] = s / (n_obs - 1)
    return cov


def _matvec(m: List[List[float]], v: List[float]) -> List[float]:
    return [sum(m[i][j] * v[j] for j in range(len(v))) for i in range(len(m))]


def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: List[float]) -> List[float]:
    n = _norm(v)
    if n < _EPSILON:
        return [1.0 / len(v)] * len(v) if v else []
    return [x / n for x in v]


def first_principal_component(matrix: List[List[float]]) -> List[float]:
    """
    First principal component of `matrix` (rows = observations, columns =
    metrics) via deterministic power iteration on the covariance matrix.

    Returns a unit vector with a fixed sign convention (largest-magnitude
    entry is positive) so repeated calls on the same data are byte-stable.
    """
    if not matrix or not matrix[0]:
        return []
    n_metrics = len(matrix[0])
    cov = _covariance_matrix(matrix)

    vec = [1.0] * n_metrics  # fixed seed, no randomness
    for _ in range(_ITERATIONS):
        vec = _matvec(cov, vec)
        vec = _normalize(vec)

    # Sign convention: flip so the largest-magnitude component is positive.
    max_idx = max(range(len(vec)), key=lambda i: abs(vec[i]))
    if vec[max_idx] < 0:
        vec = [-x for x in vec]
    return vec


def derive_category_weights(
    metric_ids: Sequence[str], observations: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    Derive intra-category weights from a project's own metric matrix.

    `observations` is a list of {metric_id: value} dicts (one per scored
    file); missing metrics in an observation are treated as 0.0. Output
    weights are non-negative (absolute loadings) and sum to 1.0, so they
    drop directly into `CompositeScoreEngine`'s intra-category weight
    slots. Falls back to equal weights when fewer than 2 observations or a
    degenerate (zero-variance) matrix is supplied.
    """
    metric_ids = list(metric_ids)
    if not metric_ids:
        return {}
    equal = 1.0 / len(metric_ids)
    if len(observations) < 2:
        return {m: equal for m in metric_ids}

    matrix = [[float(obs.get(m, 0.0)) for m in metric_ids] for obs in observations]
    loadings = first_principal_component(matrix)
    if not loadings or all(abs(x) < _EPSILON for x in loadings):
        return {m: equal for m in metric_ids}

    abs_loadings = [abs(x) for x in loadings]
    total = sum(abs_loadings)
    if total < _EPSILON:
        return {m: equal for m in metric_ids}
    return {m: w / total for m, w in zip(metric_ids, abs_loadings)}
