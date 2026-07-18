"""
Calibration unit tests (plan 10 s4 / "Testing / Bootstrapping"): a
deliberately overconfident synthetic scorer is corrected toward y=x by
isotonic regression, and its Brier score drops.
"""

import math
import random

from Asgard.Heimdall.evaluation.calibration import (
    IsotonicCalibrator,
    brier_score,
    isotonic_regression,
    reliability_diagram,
)


def test_brier_score_known_inputs():
    # Perfect predictions -> 0.0
    assert brier_score([(1.0, True), (0.0, False)]) == 0.0
    # Maximally wrong -> 1.0
    assert brier_score([(1.0, False), (0.0, True)]) == 1.0
    # Halfway confident, always right -> 0.25
    assert math.isclose(brier_score([(0.5, True), (0.5, False)]), 0.25, rel_tol=1e-9)


def test_brier_score_empty_is_zero():
    assert brier_score([]) == 0.0


def test_reliability_diagram_perfect_calibration_is_y_equals_x():
    # 100 records at 0.9 predicted, 90 of which are TP -> empirical 0.9.
    records = [(0.9, True)] * 90 + [(0.9, False)] * 10
    bins = reliability_diagram(records, n_bins=10)
    assert len(bins) == 1
    b = bins[0]
    assert math.isclose(b.predicted_mean, 0.9, rel_tol=1e-6)
    assert math.isclose(b.empirical_rate, 0.9, rel_tol=1e-6)
    assert b.count == 100


def test_reliability_diagram_bins_and_skips_empty():
    records = [(0.05, False), (0.95, True)]
    bins = reliability_diagram(records, n_bins=10)
    assert len(bins) == 2
    lowers = sorted(b.lower for b in bins)
    assert lowers == [0.0, 0.9]


def test_isotonic_regression_is_monotonic_non_decreasing():
    random.seed(42)
    x = [i / 20.0 for i in range(21)]
    # Non-monotonic noisy labels around an increasing trend.
    y = [min(1.0, max(0.0, xi + random.uniform(-0.3, 0.3))) for xi in x]
    fitted = isotonic_regression(x, y)
    for a, b in zip(fitted, fitted[1:]):
        assert a <= b + 1e-12


def test_isotonic_regression_exact_fit_on_already_monotonic_data():
    x = [0.0, 0.25, 0.5, 0.75, 1.0]
    y = [0.0, 0.25, 0.5, 0.75, 1.0]
    fitted = isotonic_regression(x, y)
    for f, expected in zip(fitted, y):
        assert math.isclose(f, expected, abs_tol=1e-9)


def test_isotonic_calibrator_corrects_overconfident_scorer_and_lowers_brier():
    # Overconfident synthetic scorer: raw score is always pinned near 1.0
    # regardless of the (monotonic-in-truth) underlying signal, i.e. a
    # scorer that says "0.95 confident" for both weak and strong true
    # positives, and never scores below 0.7 even for negatives it's
    # unsure about. True empirical TP rate for the two score levels
    # differs sharply (0.9 -> 30% true, 0.99 -> 90% true), which is
    # exactly the miscalibration isotonic regression should correct.
    random.seed(7)
    raw_scores = []
    labels = []
    for _ in range(200):
        if random.random() < 0.5:
            raw_scores.append(0.90)
            labels.append(random.random() < 0.30)
        else:
            raw_scores.append(0.99)
            labels.append(random.random() < 0.90)

    raw_brier = brier_score(list(zip(raw_scores, labels)))

    calibrator = IsotonicCalibrator().fit(raw_scores, labels)
    calibrated_records = [(calibrator.predict(s), lbl) for s, lbl in zip(raw_scores, labels)]
    calibrated_brier = brier_score(calibrated_records)

    assert calibrated_brier < raw_brier

    # Calibrated score for the 0.90 raw bucket should track its true 30%
    # empirical rate far better than the raw 0.90 does.
    calibrated_low = calibrator.predict(0.90)
    calibrated_high = calibrator.predict(0.99)
    assert calibrated_low < calibrated_high
    assert abs(calibrated_low - 0.30) < abs(0.90 - 0.30)


def test_isotonic_calibrator_predict_outside_range_clamps_to_edges():
    calibrator = IsotonicCalibrator().fit([0.2, 0.5, 0.8], [False, True, True])
    low = calibrator.predict(0.0)
    high = calibrator.predict(1.0)
    knots = calibrator.to_map()
    assert low == knots[0][1]
    assert high == knots[-1][1]


def test_isotonic_calibrator_empty_fit_is_identity():
    calibrator = IsotonicCalibrator()
    assert calibrator.predict(0.42) == 0.42
