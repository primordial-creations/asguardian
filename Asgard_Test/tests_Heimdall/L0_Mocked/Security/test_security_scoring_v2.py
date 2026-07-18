"""Tests for the multiplicative-decay security score (plan 06)."""

import random

import pytest

from Asgard.Heimdall.Security.models.security_models_base import (
    SecretFinding,
    SecretType,
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.models.security_models_findings import (
    SecretsReport,
    SecurityReport,
)
from Asgard.Heimdall.Security.normalization.scoring import (
    counts_dict,
    legacy_security_score,
    multiplicative_security_score,
    score_weight,
    size_factor,
)


def _secret(severity, confidence=0.9, path="f.py"):
    return SecretFinding(
        file_path=path, line_number=1, secret_type=SecretType.API_KEY,
        severity=severity, pattern_name="t", masked_value="*",
        line_content="t", confidence=confidence,
    )


class TestGoldenValues:
    """The four DEEPTHINK_02 walkthroughs, exact integers."""

    def test_one_critical_is_40(self):
        assert multiplicative_security_score(
            {"secrets": counts_dict(critical=1)}, 0) == 40.0

    def test_50_lows_one_category_10k_loc_is_69(self):
        assert multiplicative_security_score(
            {"container": counts_dict(low=50)}, 10_000) == 69.0

    def test_50_lows_spread_10_categories_is_56_breadth_punished(self):
        spread = {f"cat{i}": counts_dict(low=5) for i in range(10)}
        assert multiplicative_security_score(spread, 10_000) == 56.0

    def test_50_lows_1m_loc_is_96(self):
        assert multiplicative_security_score(
            {"container": counts_dict(low=50)}, 1_000_000) == 96.0

    def test_score_never_reaches_zero(self):
        score = multiplicative_security_score(
            {"secrets": counts_dict(critical=100, high=100)}, 1000)
        assert score >= 0.0
        # every fix moves the number: one fewer critical raises it
        better = multiplicative_security_score(
            {"secrets": counts_dict(critical=99, high=100)}, 1000)
        assert better >= score


class TestMonotonicity:
    """Adding any finding never raises the score; fixing never lowers it."""

    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low"])
    def test_adding_finding_never_raises(self, severity):
        rng = random.Random(42)
        for _ in range(25):
            counts = {
                f"c{i}": counts_dict(
                    critical=rng.randint(0, 3), high=rng.randint(0, 5),
                    medium=rng.randint(0, 10), low=rng.randint(0, 20),
                )
                for i in range(rng.randint(1, 5))
            }
            loc = rng.choice([0, 1000, 50_000, 1_000_000])
            before = multiplicative_security_score(counts, loc)
            counts["c0"][severity] += 1
            after = multiplicative_security_score(counts, loc)
            assert after <= before

    def test_size_factor(self):
        assert size_factor(0) == 1.0
        assert size_factor(500) == 1.0
        assert size_factor(4_000) == 2.0
        assert size_factor(1_000_000) == pytest.approx(31.6227766)

    def test_gaming_resistance_lows_cannot_offset_critical(self):
        """Fixing cheap LOWs never recovers the cost of a CRITICAL."""
        with_crit = multiplicative_security_score(
            {"a": counts_dict(critical=1)}, 10_000)
        with_crit_and_lows_fixed = multiplicative_security_score(
            {"a": counts_dict(critical=1, low=0)}, 10_000)
        many_lows_no_crit = multiplicative_security_score(
            {"a": counts_dict(low=25)}, 10_000)
        assert with_crit == with_crit_and_lows_fixed == 40.0
        assert many_lows_no_crit > with_crit


class TestScoreWeights:
    """Unlikely findings excluded; possible at 50%; test context excluded."""

    def test_unlikely_excluded(self):
        assert score_weight(0.1) == 0.0
        assert score_weight(0.24) == 0.0

    def test_possible_half_weight(self):
        assert score_weight(0.25) == 0.5
        assert score_weight(0.49) == 0.5

    def test_probable_and_certain_full(self):
        assert score_weight(0.5) == 1.0
        assert score_weight(1.0) == 1.0

    def test_no_confidence_counts_fully(self):
        """Un-triaged findings count as TPs (deliberate triage incentive)."""
        assert score_weight(None) == 1.0

    def test_test_context_excluded(self):
        assert score_weight(0.99, is_test_context=True) == 0.0


class TestReportIntegration:
    def _report(self, findings, scoring_version="v1", loc=0):
        config = SecurityScanConfig(scoring_version=scoring_version)
        report = SecurityReport(
            scan_path="/p", scan_config=config, total_lines_of_code=loc)
        secrets = SecretsReport(scan_path="/p")
        for f in findings:
            secrets.add_finding(f)
        report.secrets_report = secrets
        report.calculate_totals()
        return report

    def test_dual_reporting_both_scores_present(self):
        report = self._report([_secret(SecuritySeverity.CRITICAL)])
        assert report.legacy_score == 75.0
        assert report.security_score_v2 == 40.0
        # default follows v1 for one deprecation cycle
        assert report.security_score == 75.0

    def test_v2_flag_flips_default(self):
        report = self._report(
            [_secret(SecuritySeverity.CRITICAL)], scoring_version="v2")
        assert report.security_score == 40.0
        assert report.legacy_score == 75.0

    def test_unlikely_finding_excluded_from_v2_but_counted_in_totals(self):
        report = self._report(
            [_secret(SecuritySeverity.CRITICAL, confidence=0.1)],
            scoring_version="v2")
        assert report.critical_issues == 1        # UI counts keep everything
        assert report.security_score_v2 == 100.0  # score excludes 'unlikely'

    def test_possible_finding_half_weight(self):
        report = self._report(
            [_secret(SecuritySeverity.CRITICAL, confidence=0.3)],
            scoring_version="v2")
        # 100 * 0.4^0.5 = 63.24 -> 63
        assert report.security_score_v2 == 63.0

    def test_legacy_formula_unchanged(self):
        assert legacy_security_score(1, 1, 1, 0) == 60.0
        assert legacy_security_score(10, 0, 0, 0) == 0.0
