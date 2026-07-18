"""
Unit tests for CpuMetricsCalculator.
"""

import pytest

from Asgard.Verdandi.System import CpuMetricsCalculator


class TestCpuMetricsCalculator:
    """Tests for CpuMetricsCalculator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = CpuMetricsCalculator()

    def test_analyze_basic(self):
        """Test basic CPU analysis."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=55.0,
            core_count=4,
        )

        assert result.user_percent == 30.0
        assert result.system_percent == 15.0
        assert result.idle_percent == 55.0
        assert result.usage_percent == 45.0
        assert result.core_count == 4
        assert result.status == "healthy"

    def test_analyze_with_iowait(self):
        """Test CPU analysis with I/O wait."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=50.0,
            core_count=4,
            iowait_percent=5.0,
        )

        assert result.iowait_percent == 5.0

    def test_analyze_with_per_core_usage(self):
        """Test CPU analysis with per-core usage data."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=55.0,
            core_count=4,
            per_core_usage=[40.0, 50.0, 35.0, 55.0],
        )

        assert result.per_core_usage == [40.0, 50.0, 35.0, 55.0]

    def test_analyze_with_load_averages(self):
        """Test CPU analysis with load averages."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=55.0,
            core_count=4,
            load_average_1m=2.5,
            load_average_5m=2.2,
            load_average_15m=2.0,
        )

        assert result.load_average_1m == 2.5
        assert result.load_average_5m == 2.2
        assert result.load_average_15m == 2.0

    def test_status_healthy(self):
        """Test healthy status determination."""
        result = self.calculator.analyze(
            user_percent=40.0,
            system_percent=20.0,
            idle_percent=40.0,
            core_count=4,
        )

        assert result.status == "healthy"
        assert result.usage_percent < 80.0

    def test_status_warning(self):
        """Test warning status determination."""
        result = self.calculator.analyze(
            user_percent=60.0,
            system_percent=25.0,
            idle_percent=15.0,
            core_count=4,
        )

        assert result.status == "warning"
        assert 80.0 <= result.usage_percent < 95.0

    def test_status_critical(self):
        """Test critical status determination."""
        result = self.calculator.analyze(
            user_percent=80.0,
            system_percent=18.0,
            idle_percent=2.0,
            core_count=4,
        )

        assert result.status == "critical"
        assert result.usage_percent >= 95.0

    def test_status_warning_high_load(self):
        """Test warning status when load average is high."""
        result = self.calculator.analyze(
            user_percent=40.0,
            system_percent=20.0,
            idle_percent=40.0,
            core_count=4,
            load_average_1m=5.0,
        )

        assert result.status == "warning"

    def test_status_critical_very_high_load(self):
        """Test critical status when load average is very high."""
        result = self.calculator.analyze(
            user_percent=40.0,
            system_percent=20.0,
            idle_percent=40.0,
            core_count=4,
            load_average_1m=9.0,
        )

        assert result.status == "critical"

    def test_high_iowait_does_not_set_status(self):
        """%iowait is a CPU-state artifact (RESEARCH_12) and never sets health alone."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=30.0,
            core_count=4,
            iowait_percent=25.0,
        )

        assert result.status == "healthy"
        assert result.iowait_unreliable_on_multicore is True

    def test_calculate_load_ratio(self):
        """Test load ratio calculation."""
        ratio = self.calculator.calculate_load_ratio(
            load_average=4.0,
            core_count=4,
        )

        assert ratio == 1.0

    def test_calculate_load_ratio_overload(self):
        """Test load ratio calculation when overloaded."""
        ratio = self.calculator.calculate_load_ratio(
            load_average=8.0,
            core_count=4,
        )

        assert ratio == 2.0

    def test_calculate_load_ratio_zero_cores(self):
        """Test load ratio with zero cores returns zero."""
        ratio = self.calculator.calculate_load_ratio(
            load_average=4.0,
            core_count=0,
        )

        assert ratio == 0.0

    def test_recommendations_critical_usage(self):
        """Test recommendations for critical CPU usage."""
        result = self.calculator.analyze(
            user_percent=80.0,
            system_percent=18.0,
            idle_percent=2.0,
            core_count=4,
        )

        assert len(result.recommendations) > 0
        assert any("critical" in rec.lower() for rec in result.recommendations)

    def test_recommendations_warning_usage(self):
        """Test recommendations for warning CPU usage."""
        result = self.calculator.analyze(
            user_percent=60.0,
            system_percent=25.0,
            idle_percent=15.0,
            core_count=4,
        )

        assert len(result.recommendations) > 0
        assert any("elevated" in rec.lower() for rec in result.recommendations)

    def test_recommendations_high_iowait(self):
        """Test recommendations for high I/O wait."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=30.0,
            core_count=4,
            iowait_percent=25.0,
        )

        assert any("i/o" in rec.lower() or "wait" in rec.lower() for rec in result.recommendations)

    def test_recommendations_high_load(self):
        """Test recommendations for high load average."""
        result = self.calculator.analyze(
            user_percent=40.0,
            system_percent=20.0,
            idle_percent=40.0,
            core_count=4,
            load_average_1m=5.5,
        )

        assert any("load" in rec.lower() for rec in result.recommendations)

    def test_no_recommendations_healthy(self):
        """Test no recommendations for healthy CPU state."""
        result = self.calculator.analyze(
            user_percent=30.0,
            system_percent=15.0,
            idle_percent=55.0,
            core_count=4,
            iowait_percent=5.0,
            load_average_1m=2.0,
        )

        assert len(result.recommendations) == 0

    def test_rounding_precision(self):
        """Test that percentages are rounded to 2 decimal places."""
        result = self.calculator.analyze(
            user_percent=33.333333,
            system_percent=16.666666,
            idle_percent=50.0,
            core_count=4,
        )

        assert result.user_percent == 33.33
        assert result.system_percent == 16.67

    def test_usage_calculation(self):
        """Test that usage is calculated from idle correctly."""
        result = self.calculator.analyze(
            user_percent=35.0,
            system_percent=20.0,
            idle_percent=45.0,
            core_count=4,
        )

        assert result.usage_percent == 55.0

    def test_zero_idle(self):
        """Test analysis with zero idle CPU."""
        result = self.calculator.analyze(
            user_percent=75.0,
            system_percent=25.0,
            idle_percent=0.0,
            core_count=4,
        )

        assert result.usage_percent == 100.0
        assert result.status == "critical"

    def test_full_idle(self):
        """Test analysis with full idle CPU."""
        result = self.calculator.analyze(
            user_percent=0.0,
            system_percent=0.0,
            idle_percent=100.0,
            core_count=4,
        )

        assert result.usage_percent == 0.0
        assert result.status == "healthy"

    def test_single_core(self):
        """Test analysis with single core system."""
        result = self.calculator.analyze(
            user_percent=50.0,
            system_percent=20.0,
            idle_percent=30.0,
            core_count=1,
            load_average_1m=0.8,
        )

        assert result.core_count == 1
        assert result.status == "healthy"

    def test_many_cores(self):
        """Test analysis with many core system."""
        result = self.calculator.analyze(
            user_percent=50.0,
            system_percent=20.0,
            idle_percent=30.0,
            core_count=64,
            load_average_1m=48.0,
        )

        assert result.core_count == 64

    def test_constant_thresholds(self):
        """Test that threshold constants are correct."""
        assert CpuMetricsCalculator.WARNING_THRESHOLD == 80.0
        assert CpuMetricsCalculator.CRITICAL_THRESHOLD == 95.0

    def test_edge_case_at_warning_threshold(self):
        """Test status exactly at warning threshold."""
        result = self.calculator.analyze(
            user_percent=60.0,
            system_percent=20.0,
            idle_percent=20.0,
            core_count=4,
        )

        assert result.usage_percent == 80.0
        assert result.status == "warning"

    def test_edge_case_at_critical_threshold(self):
        """Test status exactly at critical threshold."""
        result = self.calculator.analyze(
            user_percent=75.0,
            system_percent=20.0,
            idle_percent=5.0,
            core_count=4,
        )

        assert result.usage_percent == 95.0
        assert result.status == "critical"
