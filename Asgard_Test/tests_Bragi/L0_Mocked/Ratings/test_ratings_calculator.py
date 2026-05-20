"""
Tests for Heimdall Ratings Calculator Service

Unit tests for the A-E letter ratings system covering maintainability,
reliability, and security dimensions.
"""

import pytest
from types import SimpleNamespace

from Asgard.Bragi.Ratings.models.ratings_models import (
    DebtThresholds,
    DimensionRating,
    LetterRating,
    ProjectRatings,
    RatingDimension,
    RatingsConfig,
)
from Asgard.Bragi.Ratings.services.ratings_calculator import RatingsCalculator


class TestLetterRating:
    """Tests for LetterRating enum values and ordering."""

    def test_all_values_defined(self):
        """Test that all A-E ratings are defined."""
        assert LetterRating.A.value == "A"
        assert LetterRating.B.value == "B"
        assert LetterRating.C.value == "C"
        assert LetterRating.D.value == "D"
        assert LetterRating.E.value == "E"

    def test_letter_rating_is_string_enum(self):
        """Test that LetterRating members compare as strings."""
        assert LetterRating.A == "A"
        assert LetterRating.B == "B"
        assert LetterRating.C == "C"
        assert LetterRating.D == "D"
        assert LetterRating.E == "E"

    def test_all_five_ratings_exist(self):
        """Test that exactly five ratings exist."""
        assert len(LetterRating) == 5

    def test_rating_ordering_via_calculator(self):
        """Test that the calculator treats A as best and E as worst."""
        calculator = RatingsCalculator()
        order = {
            LetterRating.A: 1,
            LetterRating.B: 2,
            LetterRating.C: 3,
            LetterRating.D: 4,
            LetterRating.E: 5,
        }
        # A should always win when A vs A
        result = calculator._derive_overall_rating(
            LetterRating.A, LetterRating.A, LetterRating.A
        )
        assert result == LetterRating.A

        # E should always win when E is present
        result = calculator._derive_overall_rating(
            LetterRating.A, LetterRating.B, LetterRating.E
        )
        assert result == LetterRating.E


class TestRatingsCalculator:
    """Tests for RatingsCalculator class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        calculator = RatingsCalculator()
        assert calculator.config is not None
        assert calculator.config.enable_maintainability is True
        assert calculator.config.enable_reliability is True
        assert calculator.config.enable_security is True

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = RatingsConfig(
            debt_thresholds=DebtThresholds(a_max=3.0, b_max=8.0, c_max=15.0, d_max=40.0)
        )
        calculator = RatingsCalculator(config)
        assert calculator.thresholds.a_max == 3.0
        assert calculator.thresholds.b_max == 8.0

    def test_calculate_from_reports_no_reports(self):
        """Test that no reports provided defaults to all A ratings."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path="./src")

        assert ratings.maintainability.rating == "A"
        assert ratings.reliability.rating == "A"
        assert ratings.security.rating == "A"
        assert ratings.overall_rating == "A"

    def test_calculate_from_reports_returns_project_ratings(self):
        """Test that calculate_from_reports returns a ProjectRatings instance."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path="./src")

        assert isinstance(ratings, ProjectRatings)
        assert ratings.scan_path == "./src"

    def test_calculate_from_reports_scan_path_recorded(self):
        """Test that scan_path is stored in the result."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path="/some/project")

        assert ratings.scan_path == "/some/project"

    def test_calculate_from_reports_scanned_at_set(self):
        """Test that scanned_at is populated."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path=".")

        assert ratings.scanned_at is not None


class TestMaintainabilityRating:
    """Tests for maintainability rating derived from debt ratio."""

    def _make_debt_report(self, debt_hours: float, total_loc: int, debt_items=None):
        """Build a minimal debt report namespace."""
        report = SimpleNamespace()
        report.total_debt_hours = debt_hours
        report.total_lines_of_code = total_loc
        report.total_debt_items = len(debt_items) if debt_items else 0
        report.debt_items = debt_items or []
        return report

    def test_maintainability_rating_a_at_zero_debt(self):
        """Test rating A when there is zero technical debt."""
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=0.0, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "A"

    def test_maintainability_rating_a_at_low_debt_ratio(self):
        """Test rating A when debt ratio is at or below 5%."""
        # 1000 LOC -> estimated 10h dev. Debt: 0.5h -> ratio 5%
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=0.5, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "A"

    def test_maintainability_rating_b(self):
        """Test rating B for debt ratio between 5% and 10%."""
        # 1000 LOC -> estimated 10h. Debt 0.8h -> ratio 8%
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=0.8, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "B"

    def test_maintainability_rating_c(self):
        """Test rating C for debt ratio between 10% and 20%."""
        # 1000 LOC -> estimated 10h. Debt 1.5h -> ratio 15%
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=1.5, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "C"

    def test_maintainability_rating_d(self):
        """Test rating D for debt ratio between 20% and 50%."""
        # 1000 LOC -> estimated 10h. Debt 3.0h -> ratio 30%
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=3.0, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "D"

    def test_maintainability_rating_e(self):
        """Test rating E for debt ratio above 50%."""
        # 1000 LOC -> estimated 10h. Debt 6.0h -> ratio 60%
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(debt_hours=6.0, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.rating == "E"

    def test_maintainability_issues_count_recorded(self):
        """Test that total debt items count is stored in rating."""
        calculator = RatingsCalculator()
        debt_report = self._make_debt_report(
            debt_hours=1.0, total_loc=1000, debt_items=["a", "b", "c"]
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.maintainability.issues_count == 3

    def test_maintainability_score_is_debt_ratio(self):
        """Test that score field reflects the calculated debt ratio."""
        calculator = RatingsCalculator()
        # 1000 LOC -> 10h estimated. 1.5h debt -> 15% ratio
        debt_report = self._make_debt_report(debt_hours=1.5, total_loc=1000)
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert abs(ratings.maintainability.score - 15.0) < 0.1

    def test_maintainability_none_report_returns_a(self):
        """Test that None debt_report yields A rating."""
        calculator = RatingsCalculator()
        dim = calculator._calculate_maintainability(None)

        assert dim.rating == "A"
        assert dim.score == 0.0

    def test_maintainability_disabled_returns_a(self):
        """Test that disabled maintainability check returns A."""
        config = RatingsConfig(enable_maintainability=False)
        calculator = RatingsCalculator(config)
        debt_report = SimpleNamespace(
            total_debt_hours=100.0,
            total_lines_of_code=100,
            total_debt_items=10,
            debt_items=[],
        )
        dim = calculator._calculate_maintainability(debt_report)

        assert dim.rating == "A"

    def test_debt_ratio_boundary_exactly_5_percent(self):
        """Test the exact boundary at 5% is still rated A."""
        calculator = RatingsCalculator()
        # 1000 LOC -> 10h. 0.5h debt -> exactly 5%
        debt_report = self._make_debt_report(debt_hours=0.5, total_loc=1000)
        dim = calculator._calculate_maintainability(debt_report)

        assert dim.rating == "A"

    def test_debt_ratio_just_above_5_percent(self):
        """Test just above 5% boundary falls into B."""
        calculator = RatingsCalculator()
        # 1000 LOC -> 10h. 0.51h -> 5.1%
        debt_report = self._make_debt_report(debt_hours=0.51, total_loc=1000)
        dim = calculator._calculate_maintainability(debt_report)

        assert dim.rating == "B"

    def test_custom_thresholds_applied(self):
        """Test that custom debt thresholds are applied correctly."""
        config = RatingsConfig(
            debt_thresholds=DebtThresholds(a_max=2.0, b_max=5.0, c_max=10.0, d_max=25.0)
        )
        calculator = RatingsCalculator(config)
        # 1000 LOC -> 10h. 0.25h -> 2.5% - above a_max of 2.0 -> B
        debt_report = SimpleNamespace(
            total_debt_hours=0.25, total_lines_of_code=1000, total_debt_items=1, debt_items=[]
        )
        dim = calculator._calculate_maintainability(debt_report)

        assert dim.rating == "B"


class TestReliabilityRating:
    """Tests for reliability rating derived from bug severity."""

    def _make_debt_item(self, severity: str):
        """Build a minimal debt item with a severity attribute."""
        item = SimpleNamespace()
        item.severity = severity
        return item

    def test_reliability_rating_a_no_bugs(self):
        """Test rating A when there are no bugs."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path=".")

        assert ratings.reliability.rating == "A"

    def test_reliability_rating_b_low_severity(self):
        """Test rating B with only low severity bugs."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[self._make_debt_item("low")],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "B"

    def test_reliability_rating_c_medium_severity(self):
        """Test rating C with medium severity bug."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[self._make_debt_item("medium")],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "C"

    def test_reliability_rating_d_high_severity(self):
        """Test rating D with high severity bug."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[self._make_debt_item("high")],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "D"

    def test_reliability_rating_e_critical_severity(self):
        """Test rating E with critical severity bug."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[self._make_debt_item("critical")],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "E"

    def test_reliability_worst_severity_wins(self):
        """Test that the worst severity across all bugs determines the rating."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=3,
            debt_items=[
                self._make_debt_item("low"),
                self._make_debt_item("high"),
                self._make_debt_item("medium"),
            ],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "D"

    def test_reliability_issues_count_from_debt_items(self):
        """Test that issues_count matches the number of debt items."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=2,
            debt_items=[
                self._make_debt_item("low"),
                self._make_debt_item("low"),
            ],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.issues_count == 2

    def test_reliability_from_quality_report_smells(self):
        """Test reliability rating from quality report detected_smells."""
        calculator = RatingsCalculator()
        smell = SimpleNamespace(severity="critical")
        quality_report = SimpleNamespace(detected_smells=[smell])
        ratings = calculator.calculate_from_reports(
            scan_path=".", quality_report=quality_report
        )

        assert ratings.reliability.rating == "E"

    def test_reliability_disabled_returns_a(self):
        """Test that disabled reliability check returns A."""
        config = RatingsConfig(enable_reliability=False)
        calculator = RatingsCalculator(config)
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[SimpleNamespace(severity="critical")],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.reliability.rating == "A"

    def test_reliability_rationale_no_bugs(self):
        """Test rationale text when no bugs found."""
        calculator = RatingsCalculator()
        dim = calculator._calculate_reliability(None, None)

        assert "No bugs" in dim.rationale or dim.rationale != ""

    def test_reliability_rationale_with_bugs(self):
        """Test rationale text when bugs are found."""
        calculator = RatingsCalculator()
        debt_report = SimpleNamespace(
            total_debt_hours=0.0,
            total_lines_of_code=100,
            total_debt_items=1,
            debt_items=[SimpleNamespace(severity="high")],
        )
        dim = calculator._calculate_reliability(None, debt_report)

        assert "HIGH" in dim.rationale
        assert "1" in dim.rationale


class TestSecurityRating:
    """Tests for security rating derived from vulnerability severity."""

    def _make_security_report(self, severities):
        """Build a minimal security report with findings."""
        findings = [SimpleNamespace(severity=s) for s in severities]
        report = SimpleNamespace()
        report.findings = findings
        return report

    def test_security_rating_a_no_vulnerabilities(self):
        """Test rating A when no vulnerabilities found."""
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(scan_path=".")

        assert ratings.security.rating == "A"

    def test_security_rating_a_none_report(self):
        """Test rating A when security report is None."""
        calculator = RatingsCalculator()
        dim = calculator._calculate_security(None)

        assert dim.rating == "A"
        assert dim.score == 0.0

    def test_security_rating_b_low_vulnerability(self):
        """Test rating B with only low severity vulnerability."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["low"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.rating == "B"

    def test_security_rating_c_medium_vulnerability(self):
        """Test rating C with medium severity vulnerability."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["medium"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.rating == "C"

    def test_security_rating_d_high_vulnerability(self):
        """Test rating D with high severity vulnerability."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["high"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.rating == "D"

    def test_security_rating_e_critical_vulnerability(self):
        """Test rating E with critical severity vulnerability."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["critical"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.rating == "E"

    def test_security_worst_severity_wins(self):
        """Test that worst severity across all findings drives the rating."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["low", "medium", "critical"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.rating == "E"

    def test_security_issues_count_recorded(self):
        """Test that the number of findings is stored in issues_count."""
        calculator = RatingsCalculator()
        security_report = self._make_security_report(["low", "medium"])
        ratings = calculator.calculate_from_reports(
            scan_path=".", security_report=security_report
        )

        assert ratings.security.issues_count == 2

    def test_security_from_vulnerabilities_attribute(self):
        """Test that 'vulnerabilities' attribute is also accepted."""
        calculator = RatingsCalculator()
        report = SimpleNamespace()
        report.vulnerabilities = [SimpleNamespace(severity="high")]
        dim = calculator._calculate_security(report)

        assert dim.rating == "D"

    def test_security_from_nested_vulnerability_report(self):
        """Test that nested vulnerability_report attribute is checked."""
        calculator = RatingsCalculator()
        inner_report = SimpleNamespace(findings=[SimpleNamespace(severity="critical")])
        outer_report = SimpleNamespace()
        outer_report.vulnerability_report = inner_report
        # No top-level findings, findings should not be empty
        outer_report.findings = []
        dim = calculator._calculate_security(outer_report)

        assert dim.rating == "E"

    def test_security_from_secrets_report(self):
        """Test that secrets_report findings are included."""
        calculator = RatingsCalculator()
        secrets_report = SimpleNamespace(findings=[SimpleNamespace(severity="high")])
        outer_report = SimpleNamespace()
        outer_report.findings = []
        outer_report.vulnerability_report = None
        outer_report.secrets_report = secrets_report
        dim = calculator._calculate_security(outer_report)

        assert dim.rating == "D"

    def test_security_disabled_returns_a(self):
        """Test that disabled security check returns A."""
        config = RatingsConfig(enable_security=False)
        calculator = RatingsCalculator(config)
        security_report = SimpleNamespace(findings=[SimpleNamespace(severity="critical")])
        dim = calculator._calculate_security(security_report)

        assert dim.rating == "A"


class TestOverallRating:
    """Tests for overall rating derivation as worst of three dimensions."""

    def test_overall_is_worst_of_three(self):
        """Test overall rating is the worst of all three dimensions."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating(
            LetterRating.A, LetterRating.C, LetterRating.B
        )
        assert result == LetterRating.C

    def test_overall_all_a_returns_a(self):
        """Test that all A dimensions yield overall A."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating(
            LetterRating.A, LetterRating.A, LetterRating.A
        )
        assert result == LetterRating.A

    def test_overall_one_e_returns_e(self):
        """Test that a single E dimension yields overall E."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating(
            LetterRating.A, LetterRating.B, LetterRating.E
        )
        assert result == LetterRating.E

    def test_overall_all_e_returns_e(self):
        """Test that all E dimensions yield overall E."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating(
            LetterRating.E, LetterRating.E, LetterRating.E
        )
        assert result == LetterRating.E

    def test_overall_d_beats_c_beats_b(self):
        """Test ordering across multiple dimension combinations."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating(
            LetterRating.B, LetterRating.D, LetterRating.C
        )
        assert result == LetterRating.D

    def test_overall_from_full_calculation(self):
        """Test overall rating in end-to-end calculation."""
        calculator = RatingsCalculator()
        # Force maintainability to E, others to A
        debt_report = SimpleNamespace(
            total_debt_hours=100.0,
            total_lines_of_code=100,
            total_debt_items=0,
            debt_items=[],
        )
        ratings = calculator.calculate_from_reports(scan_path=".", debt_report=debt_report)

        assert ratings.overall_rating == "E"

    def test_overall_string_ratings_accepted(self):
        """Test _derive_overall_rating accepts string values (from use_enum_values=True)."""
        calculator = RatingsCalculator()
        result = calculator._derive_overall_rating("A", "C", "B")
        assert result == LetterRating.C


class TestWorstSeverityHelper:
    """Tests for the internal _worst_severity helper method."""

    def test_critical_beats_high(self):
        """Test critical beats high severity."""
        calculator = RatingsCalculator()
        assert calculator._worst_severity("high", "critical") == "critical"

    def test_high_beats_medium(self):
        """Test high beats medium severity."""
        calculator = RatingsCalculator()
        assert calculator._worst_severity("medium", "high") == "high"

    def test_same_severity_returns_current(self):
        """Test same severity returns the first argument."""
        calculator = RatingsCalculator()
        result = calculator._worst_severity("medium", "medium")
        assert result == "medium"

    def test_none_current_returns_candidate(self):
        """Test None current severity returns candidate."""
        calculator = RatingsCalculator()
        assert calculator._worst_severity(None, "low") == "low"

    def test_lower_candidate_returns_current(self):
        """Test that a lower-ranked candidate does not displace current."""
        calculator = RatingsCalculator()
        assert calculator._worst_severity("high", "low") == "high"

    def test_unknown_severity_treated_as_zero(self):
        """Test that an unrecognised severity string is treated as lowest rank."""
        calculator = RatingsCalculator()
        result = calculator._worst_severity(None, "unknown_level")
        # unknown_level has order 0 which is not > 0 for current=None, but
        # the function returns current or candidate when equal
        assert result == "unknown_level"


class TestSeverityToRatingHelper:
    """Tests for the internal _severity_to_rating helper method."""

    def test_none_returns_a(self):
        """Test None severity returns A."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating(None) == LetterRating.A

    def test_info_returns_a(self):
        """Test 'info' severity returns A."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("info") == LetterRating.A

    def test_low_returns_b(self):
        """Test 'low' severity returns B."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("low") == LetterRating.B

    def test_medium_returns_c(self):
        """Test 'medium' severity returns C."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("medium") == LetterRating.C

    def test_high_returns_d(self):
        """Test 'high' severity returns D."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("high") == LetterRating.D

    def test_critical_returns_e(self):
        """Test 'critical' severity returns E."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("critical") == LetterRating.E

    def test_uppercase_severity_handled(self):
        """Test uppercase severity strings are normalised correctly."""
        calculator = RatingsCalculator()
        assert calculator._severity_to_rating("CRITICAL") == LetterRating.E
        assert calculator._severity_to_rating("HIGH") == LetterRating.D
