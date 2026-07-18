"""Heimdall Ratings Calculator - calculates A-E letter ratings for maintainability, reliability, and security."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Bragi.Ratings.models._scoring_models import MeasurementConfidence
from Asgard.Bragi.Ratings.models.ratings_models import (
    DebtThresholds,
    DimensionRating,
    LetterRating,
    ProjectRatings,
    RatingDimension,
    RatingsConfig,
)
from Asgard.Bragi.Ratings.services._report_extractors import extract_bundles
from Asgard.Bragi.Ratings.services._roi_calculator import compute_roi_actions
from Asgard.Bragi.Ratings.services.composite_score_engine import (
    CompositeScoreEngine,
    excluded_from_denominators,
)


class RatingsCalculator:
    """
    Calculates A-E quality ratings from analysis report objects.

    Accepts optional report objects from existing Heimdall analyzers and
    derives letter ratings for maintainability, reliability, and security.

    Usage:
        calculator = RatingsCalculator()
        ratings = calculator.calculate_from_reports(
            scan_path="./src",
            debt_report=debt_report,
            security_report=security_report,
        )
        print(f"Overall rating: {ratings.overall_rating}")
        print(f"Security: {ratings.security.rating}")
    """

    def __init__(self, config: Optional[RatingsConfig] = None):
        """
        Initialize the ratings calculator.

        Args:
            config: Configuration for the calculator. If None, uses defaults.
        """
        self.config = config or RatingsConfig()
        self.thresholds = self.config.debt_thresholds
        self.engine = CompositeScoreEngine()

    def calculate_from_reports(
        self,
        scan_path: str,
        debt_report=None,
        quality_report=None,
        security_report=None,
    ) -> ProjectRatings:
        """
        Calculate A-E ratings from existing Heimdall report objects.

        Args:
            scan_path: Path string of the scanned project
            debt_report: Optional DebtReport from TechnicalDebtAnalyzer
            quality_report: Optional report object for quality/reliability signals
            security_report: Optional SecurityReport from StaticSecurityService

        Returns:
            ProjectRatings with dimension ratings and overall rating
        """
        maintainability = self._calculate_maintainability(debt_report)
        reliability = self._calculate_reliability(quality_report, debt_report)
        security = self._calculate_security(security_report)

        overall = self._derive_overall_rating(maintainability.rating, reliability.rating, security.rating)

        # Composite scoring engine (Plan 01): per-file scores, risk-profile
        # aggregation, non-compensatory caps, tri-state confidence, ROI.
        file_bundles, project_bundle = extract_bundles(
            debt_report=debt_report,
            quality_report=quality_report,
            security_report=security_report,
        )
        # Plan 04 Sec.3.2: GENERATED/SUSPECTED_GENERATED files are excluded
        # from maintainability/comprehensibility denominators entirely -
        # not scored, not counted, not diluting the risk profile. Bundles
        # default to context="production" so this is a no-op unless an
        # upstream extractor stamps context (backward compatible).
        file_bundles = [b for b in file_bundles if not excluded_from_denominators(b.context)]
        file_scores = [self.engine.score_file(bundle) for bundle in file_bundles]
        for fs in file_scores:
            fs.roi_actions = compute_roi_actions(fs)
        composite_score, composite_grade, risk_profile = self.engine.score_project(
            file_scores, project_bundle
        )
        project_score = self.engine.score_file(project_bundle)
        confidence = project_score.confidence
        if composite_score is None and project_score.confidence.overall != MeasurementConfidence.NOT_MEASURED.value:
            composite_score = project_score.final_score
            composite_grade = project_score.grade
        roi_actions = compute_roi_actions(project_score)

        return ProjectRatings(
            maintainability=maintainability,
            reliability=reliability,
            security=security,
            overall_rating=overall,
            scan_path=scan_path,
            scanned_at=datetime.now(),
            composite_score=composite_score,
            composite_grade=composite_grade,
            risk_profile=risk_profile,
            file_scores=file_scores,
            confidence=confidence,
            roi_actions=roi_actions,
        )

    def _calculate_maintainability(self, debt_report) -> DimensionRating:
        """Derive maintainability rating from a DebtReport."""
        if debt_report is None or not self.config.enable_maintainability:
            return DimensionRating(
                dimension=RatingDimension.MAINTAINABILITY,
                rating=LetterRating.A,
                score=0.0,
                rationale=(
                    "No debt report provided; defaulting to A "
                    "(not assessed - this default is not evidence of quality)"
                ),
                issues_count=0,
                confidence=MeasurementConfidence.NOT_MEASURED,
            )

        issues_count = getattr(debt_report, "total_debt_items", 0) or 0
        total_debt = getattr(debt_report, "total_debt_hours", 0.0) or 0.0
        total_loc = getattr(debt_report, "total_lines_of_code", 0) or 0

        # Single source of truth: prefer the standard TDR computed by
        # TechnicalDebtAnalyzer (debt minutes / (LOC x 30 min/LOC), Plan 02).
        tdr_percent = getattr(debt_report, "tdr_percent", None)
        if tdr_percent is not None:
            debt_ratio = float(tdr_percent)
            rationale = (
                f"Technical debt ratio {debt_ratio:.2f}% "
                f"({total_debt:.1f}h debt vs 30 min/LOC development cost)"
            )
        else:
            # Legacy fallback for reports that predate the standard TDR.
            estimated_dev_hours = max(total_loc / 100.0, 1.0)
            debt_ratio = (total_debt / estimated_dev_hours) * 100.0
            rationale = (
                f"Technical debt ratio {debt_ratio:.1f}% "
                f"({total_debt:.1f}h debt / {estimated_dev_hours:.1f}h estimated; legacy estimate)"
            )

        rating = self._debt_ratio_to_rating(debt_ratio)

        return DimensionRating(
            dimension=RatingDimension.MAINTAINABILITY,
            rating=rating,
            score=round(debt_ratio, 2),
            rationale=rationale,
            issues_count=issues_count,
            confidence=MeasurementConfidence.MEASURED,
        )

    def _debt_ratio_to_rating(self, debt_ratio: float) -> LetterRating:
        """Convert a debt ratio percentage to a letter rating."""
        if debt_ratio <= self.thresholds.a_max:
            return LetterRating.A
        elif debt_ratio <= self.thresholds.b_max:
            return LetterRating.B
        elif debt_ratio <= self.thresholds.c_max:
            return LetterRating.C
        elif debt_ratio <= self.thresholds.d_max:
            return LetterRating.D
        else:
            return LetterRating.E

    def _calculate_reliability(self, quality_report, debt_report) -> DimensionRating:
        """Derive reliability rating from quality/debt report objects."""
        if not self.config.enable_reliability:
            return DimensionRating(
                dimension=RatingDimension.RELIABILITY,
                rating=LetterRating.A,
                score=0.0,
                rationale="Reliability rating disabled",
                issues_count=0,
                confidence=MeasurementConfidence.NOT_MEASURED,
            )

        if quality_report is None and debt_report is None:
            return DimensionRating(
                dimension=RatingDimension.RELIABILITY,
                rating=LetterRating.A,
                score=0.0,
                rationale=(
                    "No bugs or quality issues detected - no quality/debt report "
                    "supplied (not assessed; defaulting to A)"
                ),
                issues_count=0,
                confidence=MeasurementConfidence.NOT_MEASURED,
            )

        worst_severity = None
        issues_count = 0

        # Check debt report for high/critical items
        if debt_report is not None:
            debt_items = getattr(debt_report, "debt_items", []) or []
            issues_count = len(debt_items)
            for item in debt_items:
                severity = getattr(item, "severity", None)
                if severity is not None:
                    sev_str = str(severity).lower()
                    worst_severity = self._worst_severity(worst_severity, sev_str)

        # Check quality report if available
        if quality_report is not None:
            report_issues = getattr(quality_report, "detected_smells", []) or []
            issues_count += len(report_issues)
            for issue in report_issues:
                severity = getattr(issue, "severity", None)
                if severity is not None:
                    sev_str = str(severity).lower()
                    worst_severity = self._worst_severity(worst_severity, sev_str)

        rating = self._severity_to_rating(worst_severity)
        rationale = self._reliability_rationale(worst_severity, issues_count)
        confidence = (
            MeasurementConfidence.MEASURED
            if quality_report is not None and debt_report is not None
            else MeasurementConfidence.PARTIAL
        )

        return DimensionRating(
            dimension=RatingDimension.RELIABILITY,
            rating=rating,
            score=float(issues_count),
            rationale=rationale,
            issues_count=issues_count,
            confidence=confidence,
        )

    def _calculate_security(self, security_report) -> DimensionRating:
        """Derive security rating from a SecurityReport."""
        if security_report is None or not self.config.enable_security:
            return DimensionRating(
                dimension=RatingDimension.SECURITY,
                rating=LetterRating.A,
                score=0.0,
                rationale=(
                    "No security report provided; defaulting to A "
                    "(not assessed - this default is not evidence of security)"
                ),
                issues_count=0,
                confidence=MeasurementConfidence.NOT_MEASURED,
            )

        worst_severity = None
        total_findings = 0

        # SecurityReport may have sub-reports
        for attr in ("vulnerability_findings", "vulnerabilities", "findings"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                total_findings += len(findings)
                for finding in findings:
                    sev = getattr(finding, "severity", None)
                    if sev is not None:
                        worst_severity = self._worst_severity(worst_severity, str(sev).lower())
                break

        # Also check VulnerabilityReport if nested
        vuln_report = getattr(security_report, "vulnerability_report", None)
        if vuln_report is not None:
            for attr in ("findings", "vulnerabilities"):
                findings = getattr(vuln_report, attr, None) or []
                if findings:
                    total_findings += len(findings)
                    for finding in findings:
                        sev = getattr(finding, "severity", None)
                        if sev is not None:
                            worst_severity = self._worst_severity(worst_severity, str(sev).lower())
                    break

        # Check secrets report
        secrets_report = getattr(security_report, "secrets_report", None)
        if secrets_report is not None:
            secrets = getattr(secrets_report, "findings", []) or []
            total_findings += len(secrets)
            for secret in secrets:
                sev = getattr(secret, "severity", None)
                if sev is not None:
                    worst_severity = self._worst_severity(worst_severity, str(sev).lower())

        rating = self._severity_to_rating(worst_severity)
        rationale = self._security_rationale(worst_severity, total_findings)

        # A report object that exposes none of the known findings shapes is
        # not evidence of a clean scan - mark it PARTIAL, never MEASURED.
        has_shape = any(
            hasattr(security_report, attr)
            for attr in ("vulnerability_findings", "vulnerabilities", "findings",
                         "vulnerability_report", "secrets_report")
        )
        if not has_shape:
            rationale += " (report shape unrecognized; treated as partial evidence)"

        return DimensionRating(
            dimension=RatingDimension.SECURITY,
            rating=rating,
            score=float(total_findings),
            rationale=rationale,
            issues_count=total_findings,
            confidence=MeasurementConfidence.MEASURED if has_shape else MeasurementConfidence.PARTIAL,
        )

    def _worst_severity(self, current: Optional[str], candidate: str) -> str:
        """Return the worse of two severity strings."""
        order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
        current_val = order.get(current or "", 0)
        candidate_val = order.get(candidate, 0)
        if candidate_val > current_val:
            return candidate
        return current or candidate

    def _severity_to_rating(self, severity: Optional[str]) -> LetterRating:
        """Convert a worst-seen severity to a letter rating."""
        if severity is None:
            return LetterRating.A
        sev_lower = severity.lower()
        if sev_lower == "critical":
            return LetterRating.E
        elif sev_lower == "high":
            return LetterRating.D
        elif sev_lower == "medium":
            return LetterRating.C
        elif sev_lower == "low":
            return LetterRating.B
        else:
            return LetterRating.A

    def _reliability_rationale(self, worst_severity: Optional[str], issues_count: int) -> str:
        """Build a human-readable rationale string for the reliability rating."""
        if worst_severity is None or issues_count == 0:
            return "No bugs or quality issues detected"
        return (
            f"Worst severity issue: {worst_severity.upper()} "
            f"({issues_count} total issue(s) found)"
        )

    def _security_rationale(self, worst_severity: Optional[str], total_findings: int) -> str:
        """Build a human-readable rationale string for the security rating."""
        if worst_severity is None or total_findings == 0:
            return "No security vulnerabilities detected"
        return (
            f"Worst severity vulnerability: {worst_severity.upper()} "
            f"({total_findings} total finding(s))"
        )

    def _derive_overall_rating(
        self,
        maintainability: LetterRating,
        reliability: LetterRating,
        security: LetterRating,
    ) -> LetterRating:
        """Derive overall rating as the worst of the three dimension ratings."""
        order = {
            LetterRating.A: 1,
            LetterRating.B: 2,
            LetterRating.C: 3,
            LetterRating.D: 4,
            LetterRating.E: 5,
        }

        def _val(r):
            if isinstance(r, LetterRating):
                return order.get(r, 1)
            return order.get(LetterRating(r), 1)

        worst_val = max(_val(maintainability), _val(reliability), _val(security))
        reverse = {v: k for k, v in order.items()}
        return reverse[worst_val]
