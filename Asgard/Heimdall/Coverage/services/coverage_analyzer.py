"""
Heimdall Coverage Analyzer Service

Unified analyzer that combines all coverage analysis features.
"""

import time
from pathlib import Path
from typing import Any, List, Optional, cast

from Asgard.Heimdall.Coverage.models.coverage_models import (
    ClassCoverage,
    CoverageConfig,
    CoverageGap,
    CoverageReport,
    SuggestionPriority,
    TestSuggestion,
)
from Asgard.Heimdall.Coverage.services._coverage_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Coverage.services.gap_analyzer import GapAnalyzer
from Asgard.Heimdall.Coverage.services.suggestion_engine import SuggestionEngine


class CoverageAnalyzer:
    """
    Unified coverage analyzer combining all analysis features.

    Provides comprehensive coverage analysis including:
    - Coverage gap detection
    - Test suggestions
    - Class-level coverage
    """

    def __init__(self, config: Optional[CoverageConfig] = None):
        """Initialize the coverage analyzer."""
        self.config = config or CoverageConfig()

        self.gap_analyzer = GapAnalyzer(self.config)
        self.suggestion_engine = SuggestionEngine(self.config)

    def analyze(
        self,
        scan_path: Optional[Path] = None,
        test_path: Optional[Path] = None
    ) -> CoverageReport:
        """
        Perform complete coverage analysis.

        Args:
            scan_path: Root path to scan for source code
            test_path: Path to test files

        Returns:
            CoverageReport with all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = CoverageReport(scan_path=str(path))

        gaps, metrics, class_coverage = self.gap_analyzer.analyze(path, test_path)

        report.metrics = metrics
        report.gaps = gaps
        report.class_coverage = class_coverage

        suggestions = self.suggestion_engine.generate_suggestions(gaps)
        report.suggestions = suggestions

        report.scan_duration_seconds = time.time() - start_time

        return report

    def get_gaps(
        self,
        scan_path: Optional[Path] = None
    ) -> List[CoverageGap]:
        """
        Get coverage gaps only.

        Args:
            scan_path: Root path to scan

        Returns:
            List of coverage gaps
        """
        gaps, _, _ = self.gap_analyzer.analyze(scan_path)
        return cast(list[Any], gaps)

    def get_suggestions(
        self,
        scan_path: Optional[Path] = None,
        max_count: int = 10
    ) -> List[TestSuggestion]:
        """
        Get prioritized test suggestions.

        Args:
            scan_path: Root path to scan
            max_count: Maximum number of suggestions

        Returns:
            List of prioritized test suggestions
        """
        gaps, _, _ = self.gap_analyzer.analyze(scan_path)
        suggestions = self.suggestion_engine.generate_suggestions(gaps)
        return cast(list[Any], self.suggestion_engine.prioritize_suggestions(suggestions, max_count))

    def get_class_coverage(
        self,
        scan_path: Optional[Path] = None
    ) -> List[ClassCoverage]:
        """
        Get class-level coverage.

        Args:
            scan_path: Root path to scan

        Returns:
            List of class coverage metrics
        """
        _, _, class_coverage = self.gap_analyzer.analyze(scan_path)
        return cast(list[Any], class_coverage)

    def generate_report(
        self,
        result: CoverageReport,
        format: str = "text"
    ) -> str:
        """
        Generate a formatted report.

        Args:
            result: CoverageReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return generate_json_report(result)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)

    def quick_check(self, scan_path: Optional[Path] = None) -> dict:
        """
        Perform a quick coverage health check.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict with coverage health metrics
        """
        result = self.analyze(scan_path)

        critical_gaps = len([
            g for g in result.gaps
            if g.severity.value in ("critical", "high")
        ])

        urgent_suggestions = len([
            s for s in result.suggestions
            if s.priority in (SuggestionPriority.URGENT, SuggestionPriority.HIGH)
        ])

        return {
            "method_coverage_percent": round(result.metrics.method_coverage_percent, 2),
            "total_gaps": result.total_gaps,
            "critical_gaps": critical_gaps,
            "total_suggestions": result.total_suggestions,
            "urgent_suggestions": urgent_suggestions,
            "classes_under_50_percent": len([
                c for c in result.class_coverage
                if c.coverage_percent < 50
            ]),
        }
