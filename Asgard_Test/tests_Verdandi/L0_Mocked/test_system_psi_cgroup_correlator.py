"""
Tests for PSI analysis, CFS throttling, and USE<->RED correlation
(Plan 06: PSI/CFS/USE<->RED).
"""

from Asgard.Verdandi.System import (
    CgroupAnalyzer,
    CgroupCpuStats,
    PsiAnalyzer,
    PsiResource,
    PsiSnapshot,
    UseRedCorrelator,
)


class TestPsiAnalyzer:
    def setup_method(self):
        self.analyzer = PsiAnalyzer()

    def test_full_avg10_is_critical(self):
        snapshot = PsiSnapshot(
            resource=PsiResource.MEMORY,
            some_avg10=40.0,
            some_avg60=35.0,
            some_avg300=30.0,
            full_avg10=3.0,
            total_us=1_000_000,
        )
        report = self.analyzer.analyze(snapshot)
        assert report.severity == "critical"

    def test_cross_resource_thrashing_diagnosis(self):
        mem = PsiSnapshot(resource=PsiResource.MEMORY, full_avg10=3.0, some_avg10=40.0)
        io = PsiSnapshot(resource=PsiResource.IO, some_avg10=20.0)
        report = self.analyzer.analyze_cross_resource({"memory": mem, "io": io})
        assert report.cross_resource_diagnosis is not None
        assert "thrashing" in report.cross_resource_diagnosis

    def test_cross_resource_pure_disk_bottleneck(self):
        io = PsiSnapshot(resource=PsiResource.IO, some_avg10=20.0)
        mem = PsiSnapshot(resource=PsiResource.MEMORY, some_avg10=0.0)
        report = self.analyzer.analyze_cross_resource({"memory": mem, "io": io})
        assert "disk bottleneck" in report.cross_resource_diagnosis

    def test_fresh_spike_trajectory(self):
        snapshot = PsiSnapshot(
            resource=PsiResource.CPU, some_avg10=30.0, some_avg60=10.0, some_avg300=5.0
        )
        report = self.analyzer.analyze(snapshot)
        assert report.trajectory == "fresh_spike"


class TestCgroupAnalyzer:
    def setup_method(self):
        self.analyzer = CgroupAnalyzer()

    def test_high_throttle_ratio_is_critical_with_injected_latency(self):
        # Plan 06 L0: quota 50ms/period 100ms, nr_throttled/nr_periods=0.3
        stats = CgroupCpuStats(
            cpu_quota_us=50_000,
            cpu_period_us=100_000,
            nr_periods=1000,
            nr_throttled=300,
            throttled_time_ns=15_000_000_000,
        )
        report = self.analyzer.analyze(stats)
        assert report.verdict == "critical"
        assert report.max_injected_latency_ms == 50.0

    def test_throttling_with_idle_cores_is_limit_induced(self):
        stats = CgroupCpuStats(
            cpu_quota_us=50_000,
            cpu_period_us=100_000,
            nr_periods=1000,
            nr_throttled=100,
            throttled_time_ns=3_000_000_000,
            idle_cores_available=True,
        )
        report = self.analyzer.analyze(stats)
        assert report.limit_induced_latency is True

    def test_low_throttle_ratio_is_healthy(self):
        stats = CgroupCpuStats(
            cpu_quota_us=50_000,
            cpu_period_us=100_000,
            nr_periods=1000,
            nr_throttled=2,
            throttled_time_ns=50_000_000,
        )
        report = self.analyzer.analyze(stats)
        assert report.verdict == "healthy"


class TestUseRedCorrelator:
    def setup_method(self):
        self.correlator = UseRedCorrelator()

    def test_saturation_leads_p99_by_two_buckets(self):
        saturation = [10, 10, 80, 85, 90, 88, 87, 86]
        p99 = [50, 50, 50, 50, 300, 320, 330, 325]

        result = self.correlator.correlate(saturation, p99, max_lag=5)

        assert result.best_lag == 2
        assert result.verdict == "capacity_bound"

    def test_flat_saturation_with_rising_p99_is_regression(self):
        saturation = [20, 21, 19, 20, 21, 20, 19, 20]
        p99 = [50, 55, 70, 90, 120, 150, 180, 210]

        result = self.correlator.correlate(saturation, p99, max_lag=5)

        assert result.verdict == "regression_suspected"

    def test_insufficient_data_short_series(self):
        result = self.correlator.correlate([1, 2], [1, 2])
        assert result.verdict == "insufficient_data"
