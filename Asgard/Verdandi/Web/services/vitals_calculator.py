"""
Core Web Vitals Calculator

Calculates and rates Core Web Vitals metrics according to Google's standards.
"""

from typing import List, Optional

from Asgard.Verdandi.Web.models.web_models import (
    CoreWebVitalsInput,
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
