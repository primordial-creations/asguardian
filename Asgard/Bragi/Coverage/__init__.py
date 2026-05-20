"""
Heimdall Coverage Analysis Subpackage

Provides test coverage analysis including:
- Coverage gap detection
- Test suggestions
- Coverage trend tracking
"""

from Asgard.Bragi.Coverage.models.coverage_models import (
    CoverageConfig,
    CoverageGap,
    CoverageMetrics,
    CoverageSeverity,
    CoverageReport,
    TestSuggestion,
    SuggestionPriority,
    MethodInfo,
    ClassCoverage,
)
from Asgard.Bragi.Coverage.services.gap_analyzer import GapAnalyzer
from Asgard.Bragi.Coverage.services.suggestion_engine import SuggestionEngine
from Asgard.Bragi.Coverage.services.coverage_analyzer import CoverageAnalyzer

__all__ = [
    # Models
    "CoverageConfig",
    "CoverageGap",
    "CoverageMetrics",
    "CoverageSeverity",
    "CoverageReport",
    "TestSuggestion",
    "SuggestionPriority",
    "MethodInfo",
    "ClassCoverage",
    # Services
    "GapAnalyzer",
    "SuggestionEngine",
    "CoverageAnalyzer",
]
