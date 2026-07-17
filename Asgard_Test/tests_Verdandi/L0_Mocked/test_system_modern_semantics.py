"""
Tests for modern system semantics (Plan 06.1-06.3, RESEARCH_12).

Steal-time bands, device-class-correct iostat interpretation, memory
saturation via majflt/OOM, the thrashing-stall detector, and the demotion
of %iowait from health signal to annotation.
"""

import pytest

from Asgard.Verdandi.System import (
    CpuMetricsCalculator,
    IoMetricsCalculator,
    MemoryMetricsCalculator,
)


class TestCpuSteal:
    def setup_method(self):
        self.calc = CpuMetricsCalculator()

    def test_steal_over_5_percent_dominates_verdict(self):
        # Plan 06 L0: 6% steal with 40% total util -> CRITICAL
        result = self.calc.analyze(
            user_percent=30.0, system_percent=10.0, idle_percent=60.0,
            core_count=4, steal_percent=6.0,
        )

        assert result.status == "critical"
        assert result.steal_status == "critical"
        assert any("migrate" in r.lower() for r in result.recommendations)

    def test_steal_2_to_5_percent_warns(self):
        result = self.calc.analyze(
            user_percent=30.0, system_percent=10.0, idle_percent=60.0,
            core_count=4, steal_percent=3.0,
        )

        assert result.status == "warning"
        assert result.steal_status == "warning"

    def test_steal_under_2_percent_ok(self):
        result = self.calc.analyze(
            user_percent=30.0, system_percent=10.0, idle_percent=60.0,
            core_count=4, steal_percent=1.0,
        )

        assert result.steal_status == "ok"
        assert result.status == "healthy"

    def test_no_steal_data_leaves_field_none(self):
        result = self.calc.analyze(
            user_percent=30.0, system_percent=10.0, idle_percent=60.0,
        )

        assert result.steal_percent is None
        assert result.steal_status is None


class TestQueueingProjection:
    def setup_method(self):
        self.calc = CpuMetricsCalculator()

    def test_latency_multiplier_is_one_over_one_minus_rho(self):
        result = self.calc.analyze(
            user_percent=40.0, system_percent=10.0, idle_percent=50.0,
        )

        assert result.utilization_rho == pytest.approx(0.5)
        assert result.latency_multiplier == pytest.approx(2.0)

    def test_hockey_stick_flagged_past_80_percent(self):
        result = self.calc.analyze(
            user_percent=70.0, system_percent=15.0, idle_percent=15.0,
        )

        assert result.utilization_rho > 0.8
        assert any("hockey" in r.lower() for r in result.recommendations)

    def test_helper_method(self):
        assert self.calc.queueing_latency_multiplier(0.9) == pytest.approx(10.0)
        # Capped, never a division by zero
        assert self.calc.queueing_latency_multiplier(1.0) == pytest.approx(1000.0)


class TestIowaitDemotion:
    def test_iowait_annotated_not_status(self):
        calc = CpuMetricsCalculator()
        result = calc.analyze(
            user_percent=20.0, system_percent=10.0, idle_percent=70.0,
            core_count=8, iowait_percent=30.0,
        )

        assert result.status == "healthy"
        assert result.iowait_unreliable_on_multicore is True
        assert any("await" in r or "PSI" in r for r in result.recommendations)


class TestIoDeviceClass:
    def setup_method(self):
        self.calc = IoMetricsCalculator()

    def _analyze(self, **kwargs):
        return self.calc.analyze(
            read_bytes=1_000_000_000, write_bytes=500_000_000,
            read_ops=60_000, write_ops=30_000, duration_seconds=60,
            **kwargs,
        )

    def test_nvme_at_100_util_with_fast_awaits_is_healthy(self):
        # Plan 06 L0: NVMe %util=100, aqu-sz=2, r_await=0.3ms -> HEALTHY
        result = self._analyze(
            utilization_percent=100.0, device_type="nvme",
            aqu_sz=2.0, r_await_ms=0.3, w_await_ms=0.4,
        )

        assert result.status == "healthy"
        assert result.utilization_misleading_for_parallel_devices is True

    def test_hdd_with_identical_numbers_is_saturated(self):
        result = self._analyze(
            utilization_percent=100.0, device_type="hdd",
            aqu_sz=2.0, r_await_ms=0.3, w_await_ms=0.4,
        )

        assert result.status == "critical"
        assert result.utilization_misleading_for_parallel_devices is False

    def test_nvme_await_over_20ms_warns(self):
        result = self._analyze(device_type="nvme", r_await_ms=25.0)

        assert result.status == "warning"

    def test_nvme_await_over_50ms_critical(self):
        result = self._analyze(device_type="ssd", w_await_ms=60.0)

        assert result.status == "critical"

    def test_aqu_sz_balloon_vs_baseline_warns(self):
        result = self._analyze(
            device_type="nvme", r_await_ms=1.0,
            aqu_sz=10.0, aqu_sz_baseline=2.0,
        )

        assert result.status == "warning"
        assert any("aqu-sz" in r for r in result.recommendations)

    def test_svctm_is_discarded_with_note(self):
        result = self._analyze(device_type="nvme", svctm_ms=5.0)

        assert any("svctm" in r for r in result.recommendations)

    def test_legacy_path_without_device_type_unchanged(self):
        result = self._analyze(utilization_percent=96.0)

        assert result.status == "critical"


class TestMemorySaturation:
    def setup_method(self):
        self.calc = MemoryMetricsCalculator()

    def test_available_based_usage_preferred(self):
        # 'used' says 90% but MemAvailable says only 50% is truly unavailable
        result = self.calc.analyze(
            used_bytes=14_400_000_000, total_bytes=16_000_000_000,
            available_bytes=8_000_000_000,
        )

        assert result.available_based_usage is True
        assert result.usage_percent == pytest.approx(50.0)
        assert result.status == "healthy"

    def test_oom_kill_is_critical(self):
        result = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000, oom_kills=1,
        )

        assert result.status == "critical"
        assert any("OOM" in s for s in result.saturation_signals)

    def test_majflt_bands(self):
        warn = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000,
            major_faults_ps=50.0,
        )
        crit = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000,
            major_faults_ps=200.0,
        )

        assert warn.status == "warning"
        assert crit.status == "critical"

    def test_thrashing_stall_low_cpu_high_majflt(self):
        # Plan 06 L0: cpu=15%, majflt=500/s -> THRASHING_STALL
        result = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000,
            major_faults_ps=500.0, cpu_usage_percent=15.0,
        )

        assert result.thrashing_stall is True
        assert result.status == "critical"
        assert any("THRASHING_STALL" in r for r in result.recommendations)
        assert any("swappiness=0" in r for r in result.recommendations)

    def test_busy_cpu_high_majflt_is_not_thrashing_stall(self):
        result = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000,
            major_faults_ps=500.0, cpu_usage_percent=85.0,
        )

        assert result.thrashing_stall is False
        assert result.status == "critical"  # majflt still critical saturation

    def test_swap_churn_signal(self):
        result = self.calc.analyze(
            used_bytes=8_000_000_000, total_bytes=16_000_000_000,
            swap_in_ps=100.0, swap_out_ps=80.0,
        )

        assert any("SWAP_CHURN" in s for s in result.saturation_signals)
