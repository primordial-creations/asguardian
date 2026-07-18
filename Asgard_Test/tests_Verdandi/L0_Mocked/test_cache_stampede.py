"""
Tests for cache stampede / thundering-herd detection and XFetch advisory
(Plan 04.4).
"""

from Asgard.Verdandi.Cache import StampedeAnalyzer


class TestStampedeAnalyzer:
    def setup_method(self):
        self.analyzer = StampedeAnalyzer()

    def test_concurrent_misses_flag_stampede_with_xfetch_rule(self):
        # Plan 04 L0: 50 misses of the same key within one recompute window.
        recompute_ms = 40.0
        access_log = [
            {
                "key": "hot",
                "t": float(i) * 0.5,
                "hit": False,
                "recompute_ms": recompute_ms,
                "ttl_s": 60,
            }
            for i in range(50)
        ]

        report = self.analyzer.analyze(access_log)

        assert report.total_keys_analyzed == 1
        key_report = report.keys[0]
        assert key_report.stampede_factor == 50
        assert key_report.flagged is True
        assert key_report.delta_ms == recompute_ms
        assert key_report.xfetch_rule is not None
        assert "fetch_early" in key_report.xfetch_rule
        assert report.status in ("warning", "critical")
        assert len(report.flagged_keys) == 1

    def test_ttl_delta_sanity_flags_ttl_too_short(self):
        # Delta (recompute cost) > 10% of TTL should trip the sanity check.
        access_log = [
            {"key": "slow", "t": float(i), "hit": False, "recompute_ms": 500.0, "ttl_s": 1.0}
            for i in range(10)
        ]

        report = self.analyzer.analyze(access_log)

        key_report = report.keys[0]
        assert key_report.flagged is True
        assert key_report.ttl_too_short_for_delta is True

    def test_low_concurrency_key_not_flagged(self):
        access_log = [
            {"key": "cold", "t": 0.0, "hit": False, "recompute_ms": 10.0, "ttl_s": 300},
            {"key": "cold", "t": 1000.0, "hit": False, "recompute_ms": 10.0, "ttl_s": 300},
        ]

        report = self.analyzer.analyze(access_log)

        key_report = report.keys[0]
        assert key_report.flagged is False
        assert report.status == "healthy"
        assert report.flagged_keys == []

    def test_hits_do_not_count_as_misses(self):
        access_log = [
            {"key": "warm", "t": float(i), "hit": True, "recompute_ms": None, "ttl_s": 60}
            for i in range(20)
        ]

        report = self.analyzer.analyze(access_log)

        key_report = report.keys[0]
        assert key_report.concurrent_misses == 0
        assert key_report.stampede_factor == 0
        assert key_report.flagged is False
