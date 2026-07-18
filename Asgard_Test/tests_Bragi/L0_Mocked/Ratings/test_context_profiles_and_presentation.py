"""
Tests for Bragi Plan 04 Phases B-D: test-context scoring profile,
presentation layer (fact/heuristic + channel filtering), and suppression
telemetry built on the QualityGate suppression schema.
"""

from Asgard.Bragi.QualityGate.suppressions import parse_suppressions
from Asgard.Bragi.Ratings.models._scoring_models import FileMetricBundle, ROIAction
from Asgard.Bragi.Ratings.models.ratings_models import ChannelProfile, FindingClass
from Asgard.Bragi.Ratings.services._ratings_presenter import (
    RenderedFinding,
    assert_channel_monotonicity,
    filter_by_channel,
    render_rationale,
)
from Asgard.Bragi.Ratings.services._suppression_telemetry import build_suppression_stats
from Asgard.Bragi.Ratings.services.composite_score_engine import (
    CompositeScoreEngine,
    excluded_from_denominators,
)


class TestTestProfileScoring:
    def _bundle(self, context, cc):
        return FileMetricBundle(
            file_path="x.py", loc=100, max_cognitive_complexity=cc,
            mean_cognitive_complexity=cc, context=context,
        )

    def test_test_profile_relaxes_complexity_threshold(self):
        engine = CompositeScoreEngine()
        # 20 exceeds production threshold (15) but is under the test
        # profile's relaxed threshold (25) - test file should score higher.
        prod_score = engine.score_file(self._bundle("production", 20))
        test_score = engine.score_file(self._bundle("test", 20))
        assert test_score.final_score > prod_score.final_score

    def test_test_profile_skips_loc_penalty(self):
        engine = CompositeScoreEngine()
        prod = engine.score_file(FileMetricBundle(file_path="x.py", loc=2000, context="production"))
        test = engine.score_file(FileMetricBundle(file_path="x.py", loc=2000, context="test"))
        assert "loc_penalty" in prod.utilities
        assert "loc_penalty" not in test.utilities

    def test_default_context_is_production_backward_compat(self):
        bundle = FileMetricBundle(file_path="x.py", loc=100, max_cognitive_complexity=20)
        assert bundle.context == "production"

    def test_generated_excluded_from_denominators(self):
        assert excluded_from_denominators("generated") is True
        assert excluded_from_denominators("suspected_generated") is True
        assert excluded_from_denominators("production") is False
        assert excluded_from_denominators("test") is False
        assert excluded_from_denominators(None) is False


class TestTestHealthCategory:
    """Plan 04 Sec.3.2: assertion density, hermeticity, test-to-prod LOC ratio."""

    def test_assertion_density_only_scored_for_test_context(self):
        engine = CompositeScoreEngine()
        prod = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, context="production", assertion_density=5.0,
        ))
        test = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, context="test", assertion_density=5.0,
        ))
        assert "assertion_density" not in prod.utilities
        assert "assertion_density" in test.utilities
        assert test.utilities["assertion_density"] == 1.0

    def test_hermeticity_only_scored_for_test_context(self):
        engine = CompositeScoreEngine()
        test = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, context="test", hermeticity_score=0.9,
        ))
        assert test.utilities["hermeticity"] == 0.9

    def test_test_to_prod_ratio_only_scored_for_test_context(self):
        engine = CompositeScoreEngine()
        test = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, context="test", test_to_prod_loc_ratio=2.0,
        ))
        assert test.utilities["test_to_prod_ratio"] == 1.0

    def test_testhealth_utilities_feed_reliability_category(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, context="test",
            assertion_density=5.0, hermeticity_score=1.0, test_to_prod_loc_ratio=2.0,
        ))
        reliability = next(c for c in score.category_scores if c.category == "reliability")
        metric_ids = {u.metric_id for u in reliability.utilities}
        assert {"assertion_density", "hermeticity", "test_to_prod_ratio"} <= metric_ids

    def test_backward_compat_bundle_without_testhealth_fields(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(file_path="x.py", loc=100, context="test"))
        assert "assertion_density" not in score.utilities
        assert "hermeticity" not in score.utilities
        assert "test_to_prod_ratio" not in score.utilities


class TestPresentation:
    def test_fact_renders_as_violation(self):
        f = RenderedFinding("method_length", "65 lines; project limit 50", FindingClass.FACT)
        assert f.render() == "65 lines; project limit 50"

    def test_heuristic_renders_with_confidence(self):
        f = RenderedFinding(
            "feature_envy", "accesses 4 properties of UserAccount, none of own class",
            FindingClass.HEURISTIC, confidence=0.4,
        )
        rendered = f.render()
        assert rendered.startswith("Low confidence (40%):")

    def test_ci_gate_shows_only_facts(self):
        fact = RenderedFinding("r1", "fact msg", FindingClass.FACT)
        heuristic = RenderedFinding("r2", "heuristic msg", FindingClass.HEURISTIC, confidence=0.9)
        visible = filter_by_channel([fact, heuristic], ChannelProfile.CI_GATE)
        assert visible == [fact]

    def test_pr_review_includes_high_confidence_heuristics(self):
        heuristic = RenderedFinding("r2", "heuristic msg", FindingClass.HEURISTIC, confidence=0.9)
        visible = filter_by_channel([heuristic], ChannelProfile.PR_REVIEW)
        assert visible == [heuristic]

    def test_pr_review_excludes_low_confidence_heuristics(self):
        heuristic = RenderedFinding("r2", "heuristic msg", FindingClass.HEURISTIC, confidence=0.1)
        visible = filter_by_channel([heuristic], ChannelProfile.PR_REVIEW)
        assert visible == []

    def test_channel_monotonicity(self):
        findings = [
            RenderedFinding("r1", "fact", FindingClass.FACT),
            RenderedFinding("r2", "med heuristic", FindingClass.HEURISTIC, confidence=0.6),
            RenderedFinding("r3", "low heuristic", FindingClass.HEURISTIC, confidence=0.1),
        ]
        assert assert_channel_monotonicity(findings) is True

    def test_rationale_includes_grade_and_top_action(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="x.py", loc=100, duplication_percent=12.4,
        ))
        score.roi_actions = [
            ROIAction(metric_id="duplication", description="extract parse_config clone family",
                      score_delta=0.03),
        ]
        rationale = render_rationale(score)
        assert score.grade in rationale
        assert "extract parse_config clone family" in rationale
        assert "+0.03" in rationale


class TestSuppressionTelemetry:
    def test_valid_directives_counted_by_rule(self):
        source = (
            "# heimdall-ignore: SQLI - FP: input cast to int before query\n"
            "x = 1\n"
            "# heimdall-ignore: SQLI - FP: another false positive\n"
        )
        directives = parse_suppressions(source, file_path="a.py")
        stats = build_suppression_stats(directives, active_rule_ids={"SQLI"})
        assert stats.total_suppressions == 2
        assert stats.by_rule == {"SQLI": 2}
        assert stats.invalid_count == 0
        assert stats.unused_count == 0

    def test_bare_directive_counted_as_invalid(self):
        source = "# heimdall-ignore: SQLI\n"
        directives = parse_suppressions(source, file_path="a.py")
        stats = build_suppression_stats(directives, active_rule_ids=set())
        assert stats.invalid_count == 1
        assert stats.total_suppressions == 0

    def test_unused_suppression_detected_when_rule_no_longer_fires(self):
        source = "# heimdall-ignore: DEAD_RULE - FP: no longer applies\n"
        directives = parse_suppressions(source, file_path="a.py")
        # DEAD_RULE is not in the active rule set -> stale.
        stats = build_suppression_stats(directives, active_rule_ids={"OTHER_RULE"})
        assert stats.unused_count == 1
