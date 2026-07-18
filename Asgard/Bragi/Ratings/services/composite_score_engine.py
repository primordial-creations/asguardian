"""
Bragi Composite Score Engine

Hierarchical Gated Geometric Model (Plan 01):

1. Map raw metrics to utilities (utility_mapper).
2. Weighted Arithmetic Mean within categories (substitutable metrics).
3. Weighted Geometric Mean across categories (non-substitutable pillars).
4. Non-compensatory caps: blocker issues, extreme complexity, licenses.
5. Project score via SIG risk-profile footprints, never a mean of file scores.

Missing inputs are excluded with weight renormalization and reported via
tri-state confidence - a missing scan can never produce a silent grade A.
"""

from typing import Dict, List, Optional, Tuple

from Asgard.Bragi.Ratings.models._scoring_models import (
    CategoryScore,
    FileMetricBundle,
    FileQualityScore,
    MeasurementConfidence,
    MetricUtility,
    RiskProfile,
    ScoreCap,
    ScoreCategory,
    ScoreConfidence,
)
from Asgard.Bragi.Ratings.services import utility_mapper as um

# Inter-category default weights (DEEPTHINK_01).
DEFAULT_CATEGORY_WEIGHTS: Dict[ScoreCategory, float] = {
    ScoreCategory.RELIABILITY: 0.45,
    ScoreCategory.MAINTAINABILITY: 0.35,
    ScoreCategory.COMPREHENSIBILITY: 0.20,
}

# Grade thresholds on the final score.
GRADE_THRESHOLDS: List[Tuple[float, str]] = [
    (0.90, "A"),
    (0.80, "B"),
    (0.70, "C"),
    (0.60, "D"),
]

# Non-compensatory cap ceilings.
BLOCKER_CAP = 0.59            # grade E, inescapable while a blocker exists
EXTREME_COMPLEXITY_CAP = 0.69  # grade D
PROHIBITED_LICENSE_CAP = 0.69  # grade D
EXTREME_COMPLEXITY_THRESHOLD = 50.0

# Test-profile complexity threshold (Plan 04 Phase B / DEEPTHINK_12): DAMP,
# not DRY - cyclomatic-style thresholds relax for setup-heavy test bodies.
TEST_PROFILE_COMPLEXITY_THRESHOLD = 25.0

# Contexts excluded entirely from maintainability/comprehensibility
# denominators (Plan 04 Sec.3.2): generated code is a category error in
# these metrics. Security-relevant findings are untouched by this - the
# exclusion only applies to the Ratings scoring path.
GENERATED_CONTEXTS = frozenset({"generated", "suspected_generated"})
TEST_CONTEXTS = frozenset({"test"})


def excluded_from_denominators(context: Optional[str]) -> bool:
    """True when a file's context excludes it from Ratings scoring entirely."""
    return (context or "production") in GENERATED_CONTEXTS


def score_to_grade(score: float) -> str:
    """Map a final score in [0, 1] to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "E"


class CompositeScoreEngine:
    """Computes file-level and project-level composite quality scores."""

    def __init__(
        self,
        category_weights: Optional[Dict[ScoreCategory, float]] = None,
        complexity_threshold: float = 15.0,
    ):
        self.category_weights = dict(category_weights or DEFAULT_CATEGORY_WEIGHTS)
        self.complexity_threshold = complexity_threshold

    # ------------------------------------------------------------------ file

    def score_file(self, bundle: FileMetricBundle) -> FileQualityScore:
        """
        Score one file (or a project-level bundle) from its metric inputs.

        Context-aware (Plan 04): TEST bundles use the relaxed DAMP
        complexity threshold and skip the LOC penalty; the caller is
        responsible for excluding GENERATED bundles from the file list
        entirely (see `excluded_from_denominators`) - this method does not
        special-case GENERATED itself so it stays a pure scoring function.
        """
        utilities = self._build_utilities(bundle)
        category_scores = self._score_categories(utilities)
        base_score = self._geometric_mean(category_scores)
        cap = self._apply_gates(bundle)
        final_score = min(base_score, cap.ceiling)
        confidence = self._build_confidence(bundle, category_scores)
        grade = score_to_grade(final_score)

        rationale = f"base score {base_score:.2f} ({score_to_grade(base_score)})"
        if cap.applied and cap.ceiling < base_score:
            rationale += (
                f" capped to {final_score:.2f} ({grade}) by {cap.reason}"
                f" - fixing it restores {score_to_grade(base_score)}"
            )
        if confidence.overall != MeasurementConfidence.MEASURED:
            rationale += "; " + "; ".join(confidence.notes) if confidence.notes else ""

        return FileQualityScore(
            file_path=bundle.file_path,
            loc=bundle.loc,
            utilities={u.metric_id: u.utility for u in utilities},
            category_scores=category_scores,
            base_score=base_score,
            cap=cap,
            final_score=final_score,
            grade=grade,
            confidence=confidence,
            rationale=rationale,
        )

    def _build_utilities(self, b: FileMetricBundle) -> List[MetricUtility]:
        """Map every measured input to a MetricUtility; skip unmeasured ones."""
        utilities: List[MetricUtility] = []

        if b.bug_counts_by_severity is not None:
            weighted = um.weighted_issue_count(b.bug_counts_by_severity)
            utilities.append(MetricUtility(
                metric_id="bug_density", category=ScoreCategory.RELIABILITY,
                utility=um.count_to_utility(weighted, b.loc), weight=1.0,
                detail=f"weighted issue count {weighted:.1f} over {b.loc} LOC",
            ))

        if b.debt_ratio_percent is not None:
            utilities.append(MetricUtility(
                metric_id="debt_ratio", category=ScoreCategory.MAINTAINABILITY,
                utility=um.debt_ratio_to_utility(b.debt_ratio_percent), weight=1.0,
                detail=f"TDR {b.debt_ratio_percent:.2f}%",
            ))
        is_test = b.context in TEST_CONTEXTS
        if b.max_cognitive_complexity is not None:
            threshold = TEST_PROFILE_COMPLEXITY_THRESHOLD if is_test else self.complexity_threshold
            utilities.append(MetricUtility(
                metric_id="complexity", category=ScoreCategory.MAINTAINABILITY,
                utility=um.complexity_to_utility(
                    b.max_cognitive_complexity, b.mean_cognitive_complexity,
                    threshold=threshold,
                ),
                weight=1.0,
                detail=f"max CC {b.max_cognitive_complexity:.0f} (threshold {threshold:.0f}{' - test profile' if is_test else ''})",
            ))
        if b.duplication_percent is not None:
            utilities.append(MetricUtility(
                metric_id="duplication", category=ScoreCategory.MAINTAINABILITY,
                utility=um.bounded_to_utility(b.duplication_percent, invert=True), weight=0.5,
                detail=f"duplication {b.duplication_percent:.1f}%",
            ))
        if b.cycle_count is not None:
            utilities.append(MetricUtility(
                metric_id="cycles", category=ScoreCategory.MAINTAINABILITY,
                utility=um.cycle_count_to_utility(b.cycle_count), weight=0.5,
                detail=f"{b.cycle_count} dependency cycle(s)",
            ))
        # The LOC penalty only participates for oversized files: it is a
        # penalty for God files, not a reward for small ones, and must not
        # drag down an otherwise-unmeasured maintainability category.
        # Test profile (Plan 04 Sec.3.2): LOC penalty off - fixture-heavy
        # test files legitimately run long.
        if b.loc > 600 and b.file_path and not is_test:
            utilities.append(MetricUtility(
                metric_id="loc_penalty", category=ScoreCategory.MAINTAINABILITY,
                utility=um.loc_penalty(b.loc), weight=0.25,
                detail=f"{b.loc} LOC",
            ))

        if b.doc_coverage_percent is not None:
            utilities.append(MetricUtility(
                metric_id="doc_coverage", category=ScoreCategory.COMPREHENSIBILITY,
                utility=um.bounded_to_utility(b.doc_coverage_percent), weight=1.0,
                detail=f"doc coverage {b.doc_coverage_percent:.1f}%",
            ))
        if b.type_coverage_percent is not None:
            utilities.append(MetricUtility(
                metric_id="type_coverage", category=ScoreCategory.COMPREHENSIBILITY,
                utility=um.bounded_to_utility(b.type_coverage_percent), weight=1.0,
                detail=f"type coverage {b.type_coverage_percent:.1f}%",
            ))
        return utilities

    def _score_categories(self, utilities: List[MetricUtility]) -> List[CategoryScore]:
        """WAM within each category; unmeasured categories carry score=None."""
        scores: List[CategoryScore] = []
        for category, weight in self.category_weights.items():
            members = [u for u in utilities if u.category == category.value or u.category == category]
            if not members:
                scores.append(CategoryScore(
                    category=category, score=None, weight=weight,
                    confidence=MeasurementConfidence.NOT_MEASURED, utilities=[],
                ))
                continue
            total_w = sum(u.weight for u in members) or 1.0
            wam = sum(u.utility * u.weight for u in members) / total_w
            scores.append(CategoryScore(
                category=category, score=wam, weight=weight,
                confidence=MeasurementConfidence.MEASURED, utilities=members,
            ))
        return scores

    @staticmethod
    def _geometric_mean(category_scores: List[CategoryScore]) -> float:
        """WGM across measured categories with weight renormalization."""
        measured = [c for c in category_scores if c.score is not None]
        if not measured:
            return 0.0
        total_weight = sum(c.weight for c in measured) or 1.0
        product = 1.0
        for c in measured:
            product *= max(c.score, 0.0) ** (c.weight / total_weight)
        return min(max(product, 0.0), 1.0)

    def _apply_gates(self, b: FileMetricBundle) -> ScoreCap:
        """Non-compensatory caps; the tightest ceiling wins."""
        caps: List[Tuple[float, str]] = []
        if b.has_blocker_issue:
            reason = b.blocker_description or "a blocker/critical issue"
            caps.append((BLOCKER_CAP, reason))
        if (b.max_cognitive_complexity or 0) > EXTREME_COMPLEXITY_THRESHOLD:
            caps.append((
                EXTREME_COMPLEXITY_CAP,
                f"max cognitive complexity {b.max_cognitive_complexity:.0f} > {EXTREME_COMPLEXITY_THRESHOLD:.0f}",
            ))
        if b.prohibited_license_count > 0:
            caps.append((
                PROHIBITED_LICENSE_CAP,
                f"{b.prohibited_license_count} prohibited license(s) in dependencies",
            ))
        if not caps:
            return ScoreCap(applied=False, ceiling=1.0, reason="")
        ceiling, reason = min(caps, key=lambda c: c[0])
        return ScoreCap(applied=True, ceiling=ceiling, reason=reason)

    @staticmethod
    def _build_confidence(
        bundle: FileMetricBundle, category_scores: List[CategoryScore]
    ) -> ScoreConfidence:
        """Aggregate tri-state confidence from category coverage."""
        by_category: Dict[str, MeasurementConfidence] = {}
        notes: List[str] = []
        for c in category_scores:
            cat_name = c.category if isinstance(c.category, str) else c.category.value
            conf = c.confidence if isinstance(c.confidence, MeasurementConfidence) \
                else MeasurementConfidence(c.confidence)
            by_category[cat_name] = conf
            if conf == MeasurementConfidence.NOT_MEASURED:
                notes.append(f"{cat_name.capitalize()}: not assessed (no input supplied)")
        values = list(by_category.values())
        if all(v == MeasurementConfidence.MEASURED for v in values):
            overall = MeasurementConfidence.MEASURED
        elif all(v == MeasurementConfidence.NOT_MEASURED for v in values):
            overall = MeasurementConfidence.NOT_MEASURED
        else:
            overall = MeasurementConfidence.PARTIAL
        return ScoreConfidence(
            overall=overall,
            by_category=by_category,
            measured_sources=list(bundle.sources_present),
            missing_sources=list(bundle.sources_missing),
            notes=notes,
        )

    # --------------------------------------------------------------- project

    # Conservative LOC proxy cap for files whose real size is unknown.
    UNKNOWN_FILE_LOC_PROXY_CAP = 500

    # Risk-profile ladder thresholds (RESEARCH_05 / SIG-style defaults).
    def risk_profile(
        self, file_scores: List[FileQualityScore], total_loc: int = 0
    ) -> RiskProfile:
        """
        Distribution of LOC across grade bands over the WHOLE codebase.

        Files with unknown LOC receive a conservative proxy (the remaining
        project LOC spread across them, capped at 500 per file) and the
        profile is marked `estimated`. Project LOC not attributed to any
        finding-bearing file counts as clean (A band).
        """
        loc_by_grade: Dict[str, int] = {g: 0 for g in "ABCDE"}
        known = [fs for fs in file_scores if fs.loc > 0]
        unknown = [fs for fs in file_scores if fs.loc <= 0]
        known_loc = sum(fs.loc for fs in known)

        estimated = bool(unknown)
        remaining = max(total_loc - known_loc, 0)
        if unknown:
            proxy = max(remaining // len(unknown) if remaining else 1, 1)
            proxy = min(proxy, self.UNKNOWN_FILE_LOC_PROXY_CAP)
        else:
            proxy = 0

        for fs in known:
            loc_by_grade[fs.grade] = loc_by_grade.get(fs.grade, 0) + fs.loc
        for fs in unknown:
            loc_by_grade[fs.grade] = loc_by_grade.get(fs.grade, 0) + proxy

        attributed = sum(loc_by_grade.values())
        # Clean remainder: measured code with no findings belongs in A.
        clean = max(total_loc - attributed, 0)
        loc_by_grade["A"] = loc_by_grade.get("A", 0) + clean

        total = sum(loc_by_grade.values())
        pct_by_grade = {
            g: (100.0 * v / total if total else 0.0) for g, v in loc_by_grade.items()
        }
        return RiskProfile(
            total_loc=total, loc_by_grade=loc_by_grade,
            pct_by_grade=pct_by_grade, estimated=estimated,
        )

    @staticmethod
    def profile_to_grade(profile: RiskProfile) -> str:
        """
        Map a risk-profile footprint to a project grade.

        A requires >= 70% LOC in A/B files and 0% in E; E when > 20% LOC in E
        files; B/C/D interpolate between them.
        """
        pct = profile.pct_by_grade
        pct_e = pct.get("E", 0.0)
        pct_ab = pct.get("A", 0.0) + pct.get("B", 0.0)
        if pct_e > 20.0:
            return "E"
        if pct_e > 5.0 or pct_ab < 30.0:
            return "D"
        if pct_e > 0.0 or pct_ab < 50.0:
            return "C"
        if pct_ab < 70.0:
            return "B"
        return "A"

    def score_project(
        self, file_scores: List[FileQualityScore], project_bundle: Optional[FileMetricBundle] = None
    ) -> Tuple[Optional[float], Optional[str], RiskProfile]:
        """
        Aggregate file scores to (composite_score, grade, risk_profile).

        composite_score = min(LOC-weighted mean of file scores incl. clean
        LOC, project-level density score) - the project-density leg makes
        the score invariant to how issues are DISTRIBUTED across files, so
        splitting 400 bugs into 400 files cannot launder an E into an A.

        composite_grade = the worse of the risk-profile footprint grade and
        the grade implied by composite_score (this is the documented
        reconciliation between the two views; they can otherwise diverge
        because the footprint is a distribution and the score is a mean).

        Project-level gates from project_bundle (blocker, prohibited
        license) cap the score. Returns (None, None, empty profile) when
        there is nothing measured.
        """
        total_loc = project_bundle.loc if project_bundle is not None else 0
        profile = self.risk_profile(file_scores, total_loc=total_loc)
        if not file_scores:
            return None, None, profile
        grade = self.profile_to_grade(profile)

        scored_weight = sum(fs.loc if fs.loc > 0 else 1 for fs in file_scores)
        weighted_sum = sum(fs.final_score * (fs.loc if fs.loc > 0 else 1) for fs in file_scores)
        clean_loc = max(total_loc - sum(fs.loc for fs in file_scores if fs.loc > 0), 0) \
            if total_loc else 0
        # Clean, measured LOC scores 1.0 in the mean.
        denominator = scored_weight + clean_loc or 1
        weighted = (weighted_sum + clean_loc * 1.0) / denominator

        if project_bundle is not None:
            # Anti-laundering leg: the same issues scored at project density.
            density_score = self.score_file(project_bundle).final_score
            weighted = min(weighted, density_score)
            cap = self._apply_gates(project_bundle)
            if cap.applied:
                weighted = min(weighted, cap.ceiling)

        # Worse of footprint grade and score-implied grade (later in A..E).
        grade = max(grade, score_to_grade(weighted), key="ABCDE".index)
        return weighted, grade, profile
