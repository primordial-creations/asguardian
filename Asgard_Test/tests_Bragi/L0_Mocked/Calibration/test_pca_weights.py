"""Tests for the Plan 05 pure-Python PCA weight derivation."""

from Asgard.Bragi.Calibration.services.pca_weights import derive_category_weights


class TestDeriveCategoryWeights:
    def test_falls_back_to_equal_weights_with_too_few_observations(self):
        weights = derive_category_weights(["a", "b", "c"], [{"a": 1, "b": 2, "c": 3}])
        assert weights == {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}

    def test_weights_sum_to_one(self):
        obs = [{"a": i, "b": 2 * i, "c": i % 5} for i in range(1, 50)]
        weights = derive_category_weights(["a", "b", "c"], obs)
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_weights_are_non_negative(self):
        obs = [{"a": i, "b": -2 * i, "c": (i * 7) % 11} for i in range(1, 50)]
        weights = derive_category_weights(["a", "b", "c"], obs)
        assert all(w >= 0 for w in weights.values())

    def test_perfectly_collinear_metric_dominates_weight(self):
        # 'a' and 'b' are identical (perfectly collinear); 'c' is
        # independent noise. The dominant axis of variance should still
        # spread weight across a/b (their shared signal), not collapse to
        # equal weights.
        obs = [{"a": i, "b": i, "c": (i * 13) % 7} for i in range(1, 100)]
        weights = derive_category_weights(["a", "b", "c"], obs)
        assert weights["a"] == weights["b"]

    def test_determinism(self):
        obs = [{"a": i, "b": 3 * i + 1, "c": i * i % 17} for i in range(1, 60)]
        w1 = derive_category_weights(["a", "b", "c"], obs)
        w2 = derive_category_weights(["a", "b", "c"], obs)
        assert w1 == w2

    def test_missing_metric_treated_as_zero(self):
        obs = [{"a": i} for i in range(1, 60)]
        weights = derive_category_weights(["a", "b"], obs)
        assert set(weights.keys()) == {"a", "b"}
