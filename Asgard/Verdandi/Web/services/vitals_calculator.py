"""
Core Web Vitals Calculator

Calculates and rates Core Web Vitals metrics according to Google's standards.
"""

from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.Analysis.services.percentile_calculator import (
    PercentileCalculator,
)
from Asgard.Verdandi.Web.models.web_models import (
    CoreWebVitalsInput,
    CWVAssessment,
    VitalsDistributionResult,
    VitalsRating,
    WebVitalsResult,
)
from Asgard.Verdandi.Web.services._vitals_recommendations import (
    cls_recommendations,
    fcp_recommendations,
    fid_recommendations,
    inp_recommendations,
    lcp_recommendations,
    ttfb_recommendations,
)


class CoreWebVitalsCalculator:
    """
    Calculator for Core Web Vitals ratings.

    Rates metrics according to Google's Core Web Vitals thresholds:
    - LCP: Good < 2.5s, Needs Improvement 2.5-4s, Poor > 4s
    - FID: Good < 100ms, Needs Improvement 100-300ms, Poor > 300ms
    - CLS: Good < 0.1, Needs Improvement 0.1-0.25, Poor > 0.25
    - INP: Good < 200ms, Needs Improvement 200-500ms, Poor > 500ms
    - TTFB: Good < 800ms, Needs Improvement 800-1800ms, Poor > 1800ms
    - FCP: Good < 1.8s, Needs Improvement 1.8-3s, Poor > 3s

    Example:
        calc = CoreWebVitalsCalculator()
        result = calc.calculate(lcp_ms=2100, fid_ms=50, cls=0.05)
        print(f"Overall: {result.overall_rating}")
    """

    LCP_GOOD = 2500
    LCP_POOR = 4000

    FID_GOOD = 100
    FID_POOR = 300

    CLS_GOOD = 0.1
    CLS_POOR = 0.25

    INP_GOOD = 200
    INP_POOR = 500

    TTFB_GOOD = 800
    TTFB_POOR = 1800

    FCP_GOOD = 1800
    FCP_POOR = 3000

    #: (good_threshold, poor_threshold) per metric for distribution rating.
    THRESHOLDS = {
        "lcp": (LCP_GOOD, LCP_POOR),
        "fid": (FID_GOOD, FID_POOR),
        "cls": (CLS_GOOD, CLS_POOR),
        "inp": (INP_GOOD, INP_POOR),
        "ttfb": (TTFB_GOOD, TTFB_POOR),
        "fcp": (FCP_GOOD, FCP_POOR),
    }

    #: Core Web Vitals as of March 2024: INP replaced FID.
    CORE_METRICS = ("lcp", "inp", "cls")

    #: Minimum RUM samples before a p75 rating is meaningful (CrUX itself
    #: suppresses low-traffic segments). Below this, INSUFFICIENT_DATA is
    #: returned instead of a junk band, and it must never trip alerts.
    MIN_SAMPLES = 30

    _BAND_ORDER = {
        VitalsRating.GOOD: 0,
        VitalsRating.NEEDS_IMPROVEMENT: 1,
        VitalsRating.POOR: 2,
    }

    def rate_value(self, metric: str, value: float) -> VitalsRating:
        """Rate a single value of a metric on its tri-band thresholds."""
        try:
            good, poor = self.THRESHOLDS[metric.lower()]
        except KeyError:
            raise ValueError(
                f"Unknown metric '{metric}'; expected one of "
                f"{sorted(self.THRESHOLDS)}"
            )
        if value <= good:
            return VitalsRating.GOOD
        if value <= poor:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def assess_distribution(
        self,
        samples: Sequence[float],
        metric: str,
    ) -> VitalsDistributionResult:
        """
        Distribution-based assessment: rate the 75th percentile of RUM
        samples on the metric's tri-band, plus threshold-fraction SLIs.

        The good/ni/poor fractions merge perfectly across pages and time
        windows (the fraction over concatenated samples equals the
        traffic-weighted mean of per-window fractions) — unlike p75 values,
        which must NEVER be averaged.

        Fewer than MIN_SAMPLES samples yields rating=INSUFFICIENT_DATA
        rather than a junk band.
        """
        metric = metric.lower()
        good, poor = self.THRESHOLDS.get(metric, (None, None))
        if good is None:
            raise ValueError(
                f"Unknown metric '{metric}'; expected one of "
                f"{sorted(self.THRESHOLDS)}"
            )

        n = len(samples)
        if n < self.MIN_SAMPLES:
            return VitalsDistributionResult(
                metric=metric,
                rating=VitalsRating.INSUFFICIENT_DATA,
                sample_count=n,
                insufficient_data=True,
                recommendations=[
                    f"Only {n} samples for {metric}; at least "
                    f"{self.MIN_SAMPLES} are required for a meaningful p75 "
                    "rating. Collect more RUM data or widen the window."
                ],
            )

        p75 = PercentileCalculator().calculate_percentile(samples, 75)
        rating = self.rate_value(metric, p75)

        good_count = sum(1 for s in samples if s <= good)
        poor_count = sum(1 for s in samples if s > poor)
        good_fraction = good_count / n
        poor_fraction = poor_count / n
        ni_fraction = 1.0 - good_fraction - poor_fraction

        recommendations: List[str] = []
        if rating == VitalsRating.GOOD and poor_fraction > 0.1:
            recommendations.append(
                f"{metric}: p75 is GOOD but {poor_fraction:.0%} of samples "
                "are POOR — a tail problem. Investigate the slow "
                "device/network segment rather than the median experience."
            )
        elif rating != VitalsRating.GOOD:
            recommendations.append(
                f"{metric}: p75 itself is {rating.value} — a systemic "
                "problem affecting typical users, not just the tail."
            )

        return VitalsDistributionResult(
            metric=metric,
            p75=p75,
            rating=rating,
            good_fraction=good_fraction,
            ni_fraction=ni_fraction,
            poor_fraction=poor_fraction,
            sample_count=n,
            insufficient_data=False,
            recommendations=recommendations,
        )

    def assess_page(
        self,
        samples_by_metric: Dict[str, Sequence[float]],
    ) -> CWVAssessment:
        """
        Assess a page/origin against Core Web Vitals at the 75th percentile.

        A page passes CWV iff LCP, INP and CLS are ALL GOOD at p75 (Google's
        compliance model — vitals are never averaged into one number).
        TTFB/FCP are reported as diagnostics; FID only as a deprecated
        legacy rating (INP replaced it in March 2024).

        Origin-level rollup: pool the raw samples (or merge sketches) across
        pages before calling this; never average per-page p75s.
        """
        results: Dict[str, VitalsDistributionResult] = {
            metric: self.assess_distribution(samples, metric)
            for metric, samples in samples_by_metric.items()
            if metric.lower() in self.THRESHOLDS
        }

        core = {m: results.get(m) for m in self.CORE_METRICS}
        core_present = [r for r in core.values() if r is not None]
        core_ratable = [r for r in core_present if not r.insufficient_data]

        core_passing: Optional[bool] = None
        if len(core_ratable) == len(self.CORE_METRICS):
            core_passing = all(
                r.rating == VitalsRating.GOOD for r in core_ratable
            )
        elif any(
            r.rating in (VitalsRating.NEEDS_IMPROVEMENT, VitalsRating.POOR)
            for r in core_ratable
        ):
            # A definite core failure is decidable even with missing metrics.
            core_passing = False

        diagnostics = {
            m: r for m, r in results.items() if m not in self.CORE_METRICS
        }

        legacy_fid = results.get("fid")
        legacy_fid_rating = legacy_fid.rating if legacy_fid else None

        # Masking is a CORE-vitals concept: a composite over {LCP, INP, CLS}
        # would hide a bimodal experience. Diagnostics (TTFB/FCP) and the
        # deprecated FID never participate.
        rated_bands = [
            self._BAND_ORDER[r.rating]
            for r in core_present
            if r.rating in self._BAND_ORDER
        ]
        masking_warning = bool(rated_bands) and (
            max(rated_bands) - min(rated_bands) >= 2
        )

        recommendations: List[str] = []
        for r in results.values():
            recommendations.extend(r.recommendations)
        if masking_warning:
            recommendations.append(
                "Metric ratings disagree by 2+ bands: a composite score "
                "would mask a bimodal user experience. Evaluate each vital "
                "on its own tri-band."
            )
        if legacy_fid is not None:
            recommendations.append(
                "FID is deprecated as a Core Web Vital (replaced by INP in "
                "March 2024); its rating is reported as legacy only."
            )

        return CWVAssessment(
            lcp=core["lcp"],
            inp=core["inp"],
            cls=core["cls"],
            core_passing=core_passing,
            diagnostics=diagnostics,
            legacy_fid_rating=legacy_fid_rating,
            masking_warning=masking_warning,
            recommendations=recommendations,
        )

    def calculate(
        self,
        lcp_ms: Optional[float] = None,
        fid_ms: Optional[float] = None,
        cls: Optional[float] = None,
        inp_ms: Optional[float] = None,
        ttfb_ms: Optional[float] = None,
        fcp_ms: Optional[float] = None,
    ) -> WebVitalsResult:
        """
        Calculate Core Web Vitals ratings.

        Args:
            lcp_ms: Largest Contentful Paint in milliseconds
            fid_ms: First Input Delay in milliseconds
            cls: Cumulative Layout Shift (unitless)
            inp_ms: Interaction to Next Paint in milliseconds
            ttfb_ms: Time to First Byte in milliseconds
            fcp_ms: First Contentful Paint in milliseconds

        Returns:
            WebVitalsResult with ratings and recommendations
        """
        ratings = []
        recommendations = []

        lcp_rating = None
        if lcp_ms is not None:
            lcp_rating = self._rate_lcp(lcp_ms)
            ratings.append(lcp_rating)
            recommendations.extend(lcp_recommendations(lcp_ms, lcp_rating, self.LCP_POOR))

        fid_rating = None
        if fid_ms is not None:
            fid_rating = self._rate_fid(fid_ms)
            ratings.append(fid_rating)
            recommendations.extend(fid_recommendations(fid_ms, fid_rating))

        cls_rating = None
        if cls is not None:
            cls_rating = self._rate_cls(cls)
            ratings.append(cls_rating)
            recommendations.extend(cls_recommendations(cls, cls_rating))

        inp_rating = None
        if inp_ms is not None:
            inp_rating = self._rate_inp(inp_ms)
            ratings.append(inp_rating)
            recommendations.extend(inp_recommendations(inp_ms, inp_rating))

        ttfb_rating = None
        if ttfb_ms is not None:
            ttfb_rating = self._rate_ttfb(ttfb_ms)
            ratings.append(ttfb_rating)
            recommendations.extend(ttfb_recommendations(ttfb_ms, ttfb_rating))

        fcp_rating = None
        if fcp_ms is not None:
            fcp_rating = self._rate_fcp(fcp_ms)
            ratings.append(fcp_rating)
            recommendations.extend(fcp_recommendations(fcp_ms, fcp_rating))

        overall = self._calculate_overall(ratings)
        score = self._calculate_score(ratings)

        return WebVitalsResult(
            lcp_ms=lcp_ms,
            lcp_rating=lcp_rating,
            fid_ms=fid_ms,
            fid_rating=fid_rating,
            cls=cls,
            cls_rating=cls_rating,
            inp_ms=inp_ms,
            inp_rating=inp_rating,
            ttfb_ms=ttfb_ms,
            ttfb_rating=ttfb_rating,
            fcp_ms=fcp_ms,
            fcp_rating=fcp_rating,
            overall_rating=overall,
            score=score,
            recommendations=recommendations,
        )

    def calculate_from_input(self, input_data: CoreWebVitalsInput) -> WebVitalsResult:
        """
        Calculate from a CoreWebVitalsInput model.

        Args:
            input_data: Input data model

        Returns:
            WebVitalsResult
        """
        return self.calculate(
            lcp_ms=input_data.lcp_ms,
            fid_ms=input_data.fid_ms,
            cls=input_data.cls,
            inp_ms=input_data.inp_ms,
            ttfb_ms=input_data.ttfb_ms,
            fcp_ms=input_data.fcp_ms,
        )

    def _rate_lcp(self, lcp_ms: float) -> VitalsRating:
        """Rate LCP metric."""
        if lcp_ms <= self.LCP_GOOD:
            return VitalsRating.GOOD
        elif lcp_ms <= self.LCP_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _rate_fid(self, fid_ms: float) -> VitalsRating:
        """Rate FID metric."""
        if fid_ms <= self.FID_GOOD:
            return VitalsRating.GOOD
        elif fid_ms <= self.FID_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _rate_cls(self, cls: float) -> VitalsRating:
        """Rate CLS metric."""
        if cls <= self.CLS_GOOD:
            return VitalsRating.GOOD
        elif cls <= self.CLS_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _rate_inp(self, inp_ms: float) -> VitalsRating:
        """Rate INP metric."""
        if inp_ms <= self.INP_GOOD:
            return VitalsRating.GOOD
        elif inp_ms <= self.INP_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _rate_ttfb(self, ttfb_ms: float) -> VitalsRating:
        """Rate TTFB metric."""
        if ttfb_ms <= self.TTFB_GOOD:
            return VitalsRating.GOOD
        elif ttfb_ms <= self.TTFB_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _rate_fcp(self, fcp_ms: float) -> VitalsRating:
        """Rate FCP metric."""
        if fcp_ms <= self.FCP_GOOD:
            return VitalsRating.GOOD
        elif fcp_ms <= self.FCP_POOR:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.POOR

    def _calculate_overall(self, ratings: List[VitalsRating]) -> VitalsRating:
        """Calculate overall rating (worst of all ratings)."""
        if not ratings:
            return VitalsRating.GOOD

        if VitalsRating.POOR in ratings:
            return VitalsRating.POOR
        if VitalsRating.NEEDS_IMPROVEMENT in ratings:
            return VitalsRating.NEEDS_IMPROVEMENT
        return VitalsRating.GOOD

    def _calculate_score(self, ratings: List[VitalsRating]) -> float:
        """Calculate overall score 0-100."""
        if not ratings:
            return 100.0

        score_map = {
            VitalsRating.GOOD: 100,
            VitalsRating.NEEDS_IMPROVEMENT: 60,
            VitalsRating.POOR: 20,
        }

        total = sum(score_map[r] for r in ratings)
        return round(total / len(ratings), 1)
