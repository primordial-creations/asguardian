"""
Tests for the Bragi Composite Score Engine (Plan 01).

Covers utility-mapper math properties, WAM/WGM aggregation, non-compensatory
caps, risk-profile project aggregation, tri-state confidence (missing input
never yields silent A), ROI actions, and adversarial anti-gaming cases.
"""

from types import SimpleNamespace

import pytest

from Asgard.Bragi.Ratings.models._scoring_models import (
    FileMetricBundle,
    MeasurementConfidence,
    RiskProfile,
)
from Asgard.Bragi.Ratings.services import utility_mapper as um
from Asgard.Bragi.Ratings.services._report_extractors import extract_bundles
from Asgard.Bragi.Ratings.services._roi_calculator import compute_roi_actions
from Asgard.Bragi.Ratings.services.composite_score_engine import (
    BLOCKER_CAP,
    CompositeScoreEngine,
    score_to_grade,
)
from Asgard.Bragi.Ratings.services.ratings_calculator import RatingsCalculator


class TestUtilityMapper:
    """Property tests for the pure utility transforms."""

    def test_count_utility_monotonic_in_count(self):
        values = [um.count_to_utility(n, loc=1000) for n in (0, 1, 5, 50, 400)]
        assert values == sorted(values, reverse=True)
        assert values[0] == 1.0

    def test_count_utility_monotonic_in_loc(self):
        small = um.count_to_utility(10, loc=50)
        large = um.count_to_utility(10, loc=5000)
        assert large > small

    def test_count_utility_bounded(self):
        for n in (0, 1, 1000, 100000):
            u = um.count_to_utility(float(n), loc=100)
            assert 0.0 <= u <= 1.0

    def test_laplace_smoothing_small_file_volatility(self):
        """1 smell in a 10-line file must not score worse than 20 smells in 2000 lines."""
        tiny = um.count_to_utility(1, loc=10)
        big = um.count_to_utility(20, loc=2000)
        assert tiny >= big

    def test_severity_weighting_orders_utilities(self):
        low = um.weighted_issue_count({"low": 1})
        med = um.weighted_issue_count({"medium": 1})
        crit = um.weighted_issue_count({"critical": 1})
        assert low < med < crit

    def test_complexity_utility_perfect_below_threshold(self):
        assert um.complexity_to_utility(10, threshold=15) == 1.0

    def test_complexity_utility_decreasing(self):
        values = [um.complexity_to_utility(cc, threshold=15) for cc in (15, 20, 40, 80)]
        assert values == sorted(values, reverse=True)

    def test_bounded_utility_and_inversion(self):
        assert um.bounded_to_utility(80.0) == pytest.approx(0.8)
        assert um.bounded_to_utility(20.0, invert=True) == pytest.approx(0.8)
        assert um.bounded_to_utility(150.0) == 1.0
        assert um.bounded_to_utility(-5.0) == 0.0

    def test_loc_penalty_shape(self):
        assert um.loc_penalty(50) > 0.9
        assert um.loc_penalty(600) == pytest.approx(0.5)
        assert um.loc_penalty(5000) < 0.1


class TestEngineAggregation:
    """WAM/WGM behavior and weight renormalization."""

    def _bundle(self, **kwargs):
        defaults = dict(file_path="a.py", loc=200)
        defaults.update(kwargs)
        return FileMetricBundle(**defaults)

    def test_wgm_tends_to_zero_when_category_collapses(self):
        """WGM is non-compensatory: a near-zero category drags the base score down."""
        engine = CompositeScoreEngine()
        good = engine.score_file(self._bundle(
            bug_counts_by_severity={"medium": 1},
            doc_coverage_percent=100.0,
        ))
        bad = engine.score_file(self._bundle(
            bug_counts_by_severity={"critical": 40, "high": 100},
            doc_coverage_percent=100.0,
        ))
        assert bad.base_score < 0.2
        assert good.base_score > bad.base_score
        # Perfect docs did not compensate the destroyed reliability.
        assert bad.base_score < 0.5

    def test_missing_categories_renormalized_not_perfect(self):
        """A file measured only on reliability is scored on reliability alone."""
        engine = CompositeScoreEngine()
        score = engine.score_file(self._bundle(bug_counts_by_severity={"medium": 2}))
        measured = [c for c in score.category_scores if c.score is not None]
        assert len(measured) == 1
        assert score.base_score == pytest.approx(measured[0].score)

    def test_nothing_measured_scores_zero_not_a(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(file_path="", loc=0))
        assert score.base_score == 0.0
        assert score.confidence.overall == MeasurementConfidence.NOT_MEASURED.value
        assert score.grade == "E"

    def test_cap_never_raises_score(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(self._bundle(
            bug_counts_by_severity={"critical": 30, "high": 50, "medium": 200},
            has_blocker_issue=True,
            blocker_description="1 critical vulnerability",
        ))
        assert score.final_score <= score.base_score
        assert score.final_score <= BLOCKER_CAP


class TestNonCompensatoryGates:
    def test_blocker_caps_to_e(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="a.py", loc=50,
            bug_counts_by_severity={"low": 1},
            has_blocker_issue=True, blocker_description="1 Blocker vulnerability",
        ))
        assert score.final_score <= 0.59
        assert score.grade == "E"
        assert score.cap.applied
        assert "Blocker" in score.cap.reason

    def test_extreme_complexity_caps_to_d(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="a.py", loc=100,
            bug_counts_by_severity={},
            max_cognitive_complexity=60.0,
        ))
        assert score.final_score <= 0.69
        assert score.grade in ("D", "E")

    def test_prohibited_license_caps_to_d(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="", loc=0,
            bug_counts_by_severity={},
            prohibited_license_count=1,
        ))
        assert score.final_score <= 0.69

    def test_golden_blocker_files_differ_in_base_score(self):
        """50-line clean file with 1 blocker vs 5000-line spaghetti with 1 blocker:
        both capped <= 0.59 but base scores differ and remain visible."""
        engine = CompositeScoreEngine()
        clean = engine.score_file(FileMetricBundle(
            file_path="clean.py", loc=50,
            bug_counts_by_severity={"critical": 1},
            has_blocker_issue=True, blocker_description="1 blocker",
        ))
        spaghetti = engine.score_file(FileMetricBundle(
            file_path="mess.py", loc=5000,
            bug_counts_by_severity={"critical": 1, "high": 40, "medium": 300},
            max_cognitive_complexity=45.0,
            has_blocker_issue=True, blocker_description="1 blocker",
        ))
        assert clean.final_score <= 0.59 and spaghetti.final_score <= 0.59
        # Base scores stay distinct and visible despite the identical cap.
        assert clean.base_score != spaghetti.base_score
        assert clean.cap.applied and spaghetti.cap.applied
        # When the cap actually binds, the rationale narrates it.
        good_but_blocked = engine.score_file(FileMetricBundle(
            file_path="good.py", loc=50,
            bug_counts_by_severity={"low": 1},
            has_blocker_issue=True, blocker_description="1 blocker",
        ))
        assert "capped" in good_but_blocked.rationale


class TestAntiGaming:
    """Adversarial tests: the score must resist trivial gaming."""

    def test_400_medium_bugs_grades_worse_than_1(self):
        """The headline bug of the old model: 400 medium bugs == 1 medium bug."""
        engine = CompositeScoreEngine()
        one = engine.score_file(FileMetricBundle(
            file_path="one.py", loc=500, bug_counts_by_severity={"medium": 1}))
        many = engine.score_file(FileMetricBundle(
            file_path="many.py", loc=500, bug_counts_by_severity={"medium": 400}))
        assert many.final_score < one.final_score
        assert "ABCDE".index(many.grade) > "ABCDE".index(one.grade)

    def test_400_medium_bugs_through_ratings_calculator(self):
        """End-to-end: composite scores must differ even though the legacy
        worst-severity letters are identical."""
        calc = RatingsCalculator()

        def report(n):
            items = [SimpleNamespace(severity="medium", file_path="m.py") for _ in range(n)]
            return SimpleNamespace(
                total_debt_hours=0.0, total_lines_of_code=500,
                total_debt_items=n, debt_items=items,
            )

        one = calc.calculate_from_reports(scan_path=".", debt_report=report(1))
        many = calc.calculate_from_reports(scan_path=".", debt_report=report(400))
        assert one.reliability.rating == many.reliability.rating  # legacy surface unchanged
        assert many.composite_score < one.composite_score
        assert "ABCDE".index(many.composite_grade) >= "ABCDE".index(one.composite_grade)

    def test_padding_loc_cannot_fully_wash_out_issues(self):
        """Diluting density with LOC helps, but severity weighting keeps
        critical issues visible."""
        engine = CompositeScoreEngine()
        # The blocker gate is severity-based, not density-based.
        score = engine.score_file(FileMetricBundle(
            file_path="padded.py", loc=100000,
            bug_counts_by_severity={"critical": 3},
            has_blocker_issue=True, blocker_description="critical bugs",
        ))
        assert score.final_score <= 0.59


class TestRiskProfileAggregation:
    def _fs(self, engine, grade_target, loc):
        counts = {"A": {}, "C": {"medium": 30}, "E": {"critical": 50, "high": 100}}[grade_target]
        return engine.score_file(FileMetricBundle(
            file_path=f"{grade_target}_{loc}.py", loc=loc, bug_counts_by_severity=counts))

    def test_project_grade_from_footprint_not_mean(self):
        engine = CompositeScoreEngine()
        files = [self._fs(engine, "A", 800), self._fs(engine, "A", 800), self._fs(engine, "E", 100)]
        score, grade, profile = engine.score_project(files)
        assert profile.total_loc == 1700
        # Any E LOC forbids project A.
        assert grade != "A"

    def test_all_clean_project_is_a(self):
        engine = CompositeScoreEngine()
        files = [self._fs(engine, "A", 500) for _ in range(4)]
        score, grade, profile = engine.score_project(files)
        assert grade == "A"
        assert profile.pct_by_grade["A"] == pytest.approx(100.0)

    def test_heavy_e_footprint_is_e(self):
        engine = CompositeScoreEngine()
        files = [self._fs(engine, "E", 500), self._fs(engine, "A", 500)]
        score, grade, profile = engine.score_project(files)
        assert grade == "E"

    def test_empty_project_returns_none(self):
        engine = CompositeScoreEngine()
        score, grade, profile = engine.score_project([])
        assert score is None and grade is None
        assert profile.total_loc == 0

    def test_profile_to_grade_ladder(self):
        engine = CompositeScoreEngine()
        def grade_for(pcts):
            return engine.profile_to_grade(RiskProfile(
                total_loc=100, loc_by_grade={}, pct_by_grade=pcts))
        assert grade_for({"A": 80.0, "B": 20.0, "E": 0.0}) == "A"
        assert grade_for({"A": 60.0, "C": 40.0, "E": 0.0}) == "B"
        assert grade_for({"A": 40.0, "C": 60.0, "E": 0.0}) == "C"
        assert grade_for({"A": 20.0, "C": 74.0, "E": 6.0}) == "D"
        assert grade_for({"A": 50.0, "E": 25.0}) == "E"


class TestConfidence:
    """Never reward ignorance: absent inputs are reported, not defaulted to A."""

    def test_no_security_report_marks_not_measured(self):
        calc = RatingsCalculator()
        ratings = calc.calculate_from_reports(scan_path=".")
        assert ratings.security.confidence == MeasurementConfidence.NOT_MEASURED.value
        assert ratings.maintainability.confidence == MeasurementConfidence.NOT_MEASURED.value
        assert ratings.reliability.confidence == MeasurementConfidence.NOT_MEASURED.value
        # Nothing measured -> no composite score is invented.
        assert ratings.composite_score is None
        assert ratings.confidence is not None
        assert ratings.confidence.overall == MeasurementConfidence.NOT_MEASURED.value
        assert ratings.confidence.missing_sources == [
            "debt_report", "quality_report", "security_report"]

    def test_partial_inputs_marked_partial(self):
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=1.0, total_lines_of_code=1000,
            total_debt_items=1,
            debt_items=[SimpleNamespace(severity="low", file_path="x.py")],
        )
        ratings = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        assert ratings.security.confidence == MeasurementConfidence.NOT_MEASURED.value
        assert ratings.reliability.confidence == MeasurementConfidence.PARTIAL.value
        assert "security_report" in ratings.confidence.missing_sources
        assert ratings.composite_score is not None

    def test_not_measured_annotated_in_rationale(self):
        calc = RatingsCalculator()
        dim = calc._calculate_security(None)
        assert "not assessed" in dim.rationale

    def test_tdr_percent_preferred_over_legacy_estimate(self):
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=10.0, total_lines_of_code=1000,
            total_debt_items=0, debt_items=[], tdr_percent=6.38,
        )
        dim = calc._calculate_maintainability(debt_report)
        assert dim.score == pytest.approx(6.38)
        assert dim.rating == "B"


class TestROIActions:
    def test_cap_lifting_action_ranked_first(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="a.py", loc=100,
            bug_counts_by_severity={"low": 1},
            doc_coverage_percent=90.0,
            has_blocker_issue=True, blocker_description="1 Blocker vulnerability",
        ))
        actions = compute_roi_actions(score)
        assert actions
        assert actions[0].lifts_cap is True
        assert actions[0].score_delta > 0

    def test_actions_sorted_descending(self):
        engine = CompositeScoreEngine()
        score = engine.score_file(FileMetricBundle(
            file_path="a.py", loc=300,
            bug_counts_by_severity={"medium": 20},
            doc_coverage_percent=10.0,
            max_cognitive_complexity=30.0,
        ))
        actions = compute_roi_actions(score)
        deltas = [a.score_delta for a in actions]
        assert deltas == sorted(deltas, reverse=True)
        assert all(d > 0 for d in deltas)


class TestDeterminism:
    def test_same_inputs_same_outputs(self):
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=3.0, total_lines_of_code=2000, total_debt_items=2,
            debt_items=[
                SimpleNamespace(severity="medium", file_path="a.py"),
                SimpleNamespace(severity="high", file_path="b.py"),
            ],
        )
        r1 = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        r2 = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        assert r1.composite_score == r2.composite_score
        assert [f.final_score for f in r1.file_scores] == [f.final_score for f in r2.file_scores]


class TestExtractors:
    def test_extract_bundles_records_sources(self):
        bundles, project = extract_bundles()
        assert bundles == []
        assert project.sources_missing == ["debt_report", "quality_report", "security_report"]

    def test_critical_security_finding_sets_blocker(self):
        report = SimpleNamespace(findings=[
            SimpleNamespace(severity="critical", file_path="s.py", description="RCE")])
        bundles, project = extract_bundles(security_report=report)
        assert project.has_blocker_issue is True
        assert "critical" in project.blocker_description

    def test_grade_thresholds(self):
        assert score_to_grade(0.95) == "A"
        assert score_to_grade(0.85) == "B"
        assert score_to_grade(0.75) == "C"
        assert score_to_grade(0.65) == "D"
        assert score_to_grade(0.30) == "E"


class TestAdversarialReviewRegressions:
    """Regressions from the adversarial review (BLOCKERs 4-5, MAJORs 6, 12-13)."""

    def test_critical_debt_item_does_not_trigger_blocker_cap(self):
        """BLOCKER-4: a critical DEBT item (e.g. CC>30) must not cap the
        project at E; the blocker cap is reserved for bugs/vulnerabilities."""
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=2.0, total_lines_of_code=5000, total_debt_items=1,
            debt_items=[SimpleNamespace(
                severity="critical", file_path="big.py",
                description="High complexity function")],
        )
        ratings = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        # Heavily penalized via severity-weighted density, but not E-capped.
        for fs in ratings.file_scores:
            assert fs.cap.applied is False
        from Asgard.Bragi.Ratings.services._report_extractors import extract_bundles
        _, project = extract_bundles(debt_report=debt_report)
        assert project.has_blocker_issue is False

    def test_critical_security_finding_still_blocks(self):
        """Counterpart: critical VULNERABILITIES do trigger the blocker cap."""
        report = SimpleNamespace(findings=[
            SimpleNamespace(severity="critical", file_path="s.py", description="RCE")])
        bundles, project = extract_bundles(security_report=report)
        assert project.has_blocker_issue is True
        assert bundles[0].has_blocker_issue is True

    def test_file_splitting_cannot_launder_grade(self):
        """BLOCKER-5: 400 medium bugs split across 400 files must grade like
        400 bugs in one file, not like a clean project."""
        calc = RatingsCalculator()

        def report(n_files):
            items = [SimpleNamespace(severity="medium", file_path=f"f{i}.py")
                     for i in range(400)] if n_files == 400 else \
                    [SimpleNamespace(severity="medium", file_path="one.py")
                     for _ in range(400)]
            return SimpleNamespace(
                total_debt_hours=0.0, total_lines_of_code=500,
                total_debt_items=400, debt_items=items)

        concentrated = calc.calculate_from_reports(scan_path=".", debt_report=report(1))
        split = calc.calculate_from_reports(scan_path=".", debt_report=report(400))
        assert split.composite_grade == concentrated.composite_grade == "E"
        assert split.composite_score == pytest.approx(concentrated.composite_score, abs=0.05)

    def test_tiny_e_file_does_not_sink_huge_clean_project(self):
        """MAJOR-6: the footprint spans total LOC including clean code."""
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=1.0, total_lines_of_code=100000, total_debt_items=40,
            debt_items=[SimpleNamespace(severity="medium", file_path="bad.py")
                        for _ in range(40)],
        )
        ratings = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        assert ratings.composite_grade != "E"
        assert ratings.risk_profile.total_loc == 100000
        assert ratings.risk_profile.estimated is True  # per-file LOC proxied

    def test_risk_profile_counts_clean_loc_as_a(self):
        engine = CompositeScoreEngine()
        bad = engine.score_file(FileMetricBundle(
            file_path="bad.py", loc=100,
            bug_counts_by_severity={"critical": 50, "high": 100}))
        profile = engine.risk_profile([bad], total_loc=10000)
        assert profile.loc_by_grade["A"] == 9900
        assert profile.loc_by_grade["E"] == 100
        assert profile.estimated is False

    def test_shapeless_security_report_is_partial_not_measured(self):
        """MINOR-12: an empty duck-typed report is not evidence of a scan."""
        calc = RatingsCalculator()
        dim = calc._calculate_security(SimpleNamespace())
        assert dim.confidence == MeasurementConfidence.PARTIAL.value
        assert dim.rating == "A"  # legacy letter preserved
        shaped = calc._calculate_security(SimpleNamespace(findings=[]))
        assert shaped.confidence == MeasurementConfidence.MEASURED.value

    def test_composite_grade_never_better_than_score_grade(self):
        """MINOR-13 reconciliation: grade = worse of footprint and score."""
        calc = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0, total_lines_of_code=500, total_debt_items=200,
            debt_items=[SimpleNamespace(severity="high", file_path=f"f{i}.py")
                        for i in range(200)],
        )
        ratings = calc.calculate_from_reports(scan_path=".", debt_report=debt_report)
        from Asgard.Bragi.Ratings.services.composite_score_engine import score_to_grade
        assert "ABCDE".index(ratings.composite_grade) >= \
            "ABCDE".index(score_to_grade(ratings.composite_score))
