"""
Verdandi Web - Web Performance Metrics

This module provides web performance metric calculations including:
- Core Web Vitals (LCP, FID, CLS, INP, TTFB)
- Navigation timing metrics
- Resource timing analysis
- Paint timing (FP, FCP)

Usage:
    from Asgard.Verdandi.Web import CoreWebVitalsCalculator

    calc = CoreWebVitalsCalculator()
    result = calc.calculate(lcp_ms=2100, fid_ms=50, cls=0.05)
    print(f"LCP Rating: {result.lcp_rating}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Web.models.web_models import (
    CoreWebVitalsInput,
    CWVAssessment,
    VitalsDistributionInput,
    VitalsDistributionResult,
    NavigationTimingInput,
    ResourceTimingInput,
    VitalsRating,
    WebVitalsResult,
    NavigationTimingResult,
    ResourceTimingResult,
)
from Asgard.Verdandi.Web.services.vitals_calculator import CoreWebVitalsCalculator
from Asgard.Verdandi.Web.services.navigation_timing import NavigationTimingCalculator
from Asgard.Verdandi.Web.services.resource_timing import ResourceTimingCalculator

__all__ = [
    "CoreWebVitalsCalculator",
    "CoreWebVitalsInput",
    "CWVAssessment",
    "VitalsDistributionInput",
    "VitalsDistributionResult",
    "NavigationTimingCalculator",
    "NavigationTimingInput",
    "NavigationTimingResult",
    "ResourceTimingCalculator",
    "ResourceTimingInput",
    "ResourceTimingResult",
    "VitalsRating",
    "WebVitalsResult",
]
