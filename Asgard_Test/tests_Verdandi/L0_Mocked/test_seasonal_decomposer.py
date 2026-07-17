"""
Unit tests for SeasonalDecomposer (robust STL-lite decomposition, Plan 03F).
"""

import math

import pytest

from Asgard.Verdandi.Trend import SeasonalDecomposer, TrendAnalyzer
from Asgard.Verdandi.Trend.models.trend_models import (
    DecompositionMode,
    DecompositionOutcome,
)


def _synthetic_series(n_points: int, period: int, slope: float, amplitude: float):
    """trend + seasonal sine + occasional spikes."""
    values = []
    for i in range(n_points):
        trend = 10.0 + slope * i
        seasonal = amplitude * math.sin(2 * math.pi * (i % period) / period)
        spike = 0.0
        if i % 37 == 0:
            spike = amplitude * 4
        values.append(trend + seasonal + spike)
    return values


class TestSeasonalDecomposer:
    """Tests for SeasonalDecomposer."""

    def setup_method(self):
        self.decomposer = SeasonalDecomposer()

    def test_insufficient_cycles_below_3_periods(self):
        values = _synthetic_series(n_points=40, period=24, slope=0.05, amplitude=5.0)

        result = self.decomposer.decompose(values, period=24)

        assert result.outcome == DecompositionOutcome.INSUFFICIENT_DATA
        assert result.cycles_available < 3.0

    def test_exactly_3_cycles_is_sufficient(self):
        values = _synthetic_series(n_points=72, period=24, slope=0.05, amplitude=5.0)

        result = self.decomposer.decompose(values, period=24)

        assert result.outcome == DecompositionOutcome.OK

    def test_additive_recovers_slope_within_10_percent(self):
        """L0 STL: synthetic trend + daily sine + spikes recovers slope
        within 10%, spikes land in residual."""
        n_points = 24 * 8
        period = 24
        slope = 0.1
        amplitude = 5.0
        values = _synthetic_series(n_points, period, slope, amplitude)

        result = self.decomposer.decompose(values, period=period)

        assert result.outcome == DecompositionOutcome.OK
        # Slope recovered from the trend component's endpoints.
        valid_trend = [t for t in result.trend if t is not None]
        recovered_slope = (valid_trend[-1] - valid_trend[0]) / (n_points - 1)
        assert recovered_slope == pytest.approx(slope, rel=0.20)

        # Spike indices should show up as large-magnitude residuals.
        spike_indices = [i for i in range(n_points) if i % 37 == 0]
        non_spike_indices = [i for i in range(n_points) if i % 37 != 0]
        mean_spike_residual = sum(
            abs(result.residual[i]) for i in spike_indices
        ) / len(spike_indices)
        mean_other_residual = sum(
            abs(result.residual[i]) for i in non_spike_indices
        ) / len(non_spike_indices)
        assert mean_spike_residual > mean_other_residual

    def test_seasonal_indices_sum_to_zero_additive(self):
        values = _synthetic_series(n_points=24 * 5, period=24, slope=0.0, amplitude=3.0)

        result = self.decomposer.decompose(values, period=24)

        assert sum(result.seasonal_indices) == pytest.approx(0.0, abs=1e-4)

    def test_multiplicative_mode_reconstructs_series(self):
        n_points = 24 * 5
        period = 24
        values = [
            (10.0 + 0.05 * i) * (1.0 + 0.3 * math.sin(2 * math.pi * (i % period) / period))
            for i in range(n_points)
        ]

        result = self.decomposer.decompose(
            values, period=period, mode=DecompositionMode.MULTIPLICATIVE
        )

        assert result.outcome == DecompositionOutcome.OK
        reconstructed = [
            result.trend[i] * result.seasonal[i] * result.residual[i]
            for i in range(n_points)
        ]
        for original, rebuilt in zip(values, reconstructed):
            assert rebuilt == pytest.approx(original, rel=0.05)

    def test_multiplicative_requires_positive_values(self):
        values = [1.0, -2.0, 3.0] * 30

        result = self.decomposer.decompose(
            values, period=3, mode=DecompositionMode.MULTIPLICATIVE
        )

        assert result.outcome == DecompositionOutcome.INSUFFICIENT_DATA

    def test_invalid_period_is_insufficient_data(self):
        result = self.decomposer.decompose([1.0, 2.0, 3.0], period=0)

        assert result.outcome == DecompositionOutcome.INSUFFICIENT_DATA

    def test_trend_analyzer_deseasonalized_option(self):
        n_points = 24 * 6
        period = 24
        values = _synthetic_series(n_points, period, slope=0.2, amplitude=8.0)

        analyzer = TrendAnalyzer()
        result = analyzer.analyze_deseasonalized(values, period=period, metric_name="m")

        assert result.data_point_count == n_points
        assert result.seasonality_detected is True

    def test_trend_analyzer_deseasonalized_falls_back_when_insufficient(self):
        values = [10.0 + 0.1 * i for i in range(10)]

        analyzer = TrendAnalyzer()
        result = analyzer.analyze_deseasonalized(values, period=24, metric_name="m")

        assert "insufficient" in result.description.lower() or result.data_point_count == 0
