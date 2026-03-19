"""
Heimdall Coverage Analyzer Service

Unified analyzer that combines all coverage analysis features.
"""

import json
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Coverage.models.coverage_models import (
    ClassCoverage,
    CoverageConfig,
    CoverageGap,
    CoverageReport,
    SuggestionPriority,
    TestSuggestion,
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

        # Initialize sub-analyzers
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

        # Analyze gaps
        gaps, metrics, class_coverage = self.gap_analyzer.analyze(path, test_path)

        report.metrics = metrics
        report.gaps = gaps
        report.class_coverage = class_coverage

        # Generate suggestions
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
        return gaps

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
        return self.suggestion_engine.prioritize_suggestions(suggestions, max_count)

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
        return class_coverage

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
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: CoverageReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL COVERAGE ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:        {result.scan_path}")
        lines.append(f"  Scanned At:       {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Duration:         {result.scan_duration_seconds:.2f}s")
        lines.append("")

        # Metrics
        lines.append("-" * 70)
        lines.append("  COVERAGE METRICS")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"  Total Methods:      {result.metrics.total_methods}")
        lines.append(f"  Covered Methods:    {result.metrics.covered_methods}")
        lines.append(f"  Method Coverage:    {result.metrics.method_coverage_percent:.1f}%")
        if result.metrics.total_branches > 0:
            lines.append(f"  Total Branches:     {result.metrics.total_branches}")
            lines.append(f"  Branch Coverage:    {result.metrics.branch_coverage_percent:.1f}%")
        lines.append("")

        # Gaps summary
        if result.gaps:
            lines.append("-" * 70)
            lines.append("  COVERAGE GAPS")
            lines.append("-" * 70)
            lines.append("")

            for severity, gaps in result.gaps_by_severity.items():
                if gaps:
                    lines.append(f"  {severity.value.upper()}: {len(gaps)} gaps")

            lines.append("")

            # Top gaps
            lines.append("  Top Gaps:")
            for gap in result.gaps[:5]:
                lines.append(f"    [{gap.severity.value.upper()}] {gap.method.full_name}")
                lines.append(f"      File: {gap.file_path}:{gap.line_number}")

            lines.append("")

        # Suggestions
        if result.suggestions:
            lines.append("-" * 70)
            lines.append("  TEST SUGGESTIONS")
            lines.append("-" * 70)
            lines.append("")

            for priority, suggestions in result.suggestions_by_priority.items():
                if suggestions:
                    lines.append(f"  {priority.value.upper()}: {len(suggestions)} suggestions")

            lines.append("")

            # Top suggestions
            lines.append("  Top Suggestions:")
            for sug in result.suggestions[:5]:
                lines.append(f"    [{sug.priority.value.upper()}] {sug.test_name}")
                lines.append(f"      {sug.description}")

            lines.append("")

        # Class coverage
        if result.class_coverage:
            # Find poorly covered classes
            poor = [c for c in result.class_coverage if c.coverage_percent < 50]
            if poor:
                lines.append("-" * 70)
                lines.append("  CLASSES NEEDING ATTENTION")
                lines.append("-" * 70)
                lines.append("")

                for cls in sorted(poor, key=lambda c: c.coverage_percent)[:5]:
                    lines.append(f"  {cls.class_name}: {cls.coverage_percent:.1f}% coverage")
                    lines.append(f"    Uncovered: {', '.join(cls.uncovered_methods[:3])}")

                lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: CoverageReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "scan_duration_seconds": result.scan_duration_seconds,
            "metrics": {
                "total_methods": result.metrics.total_methods,
                "covered_methods": result.metrics.covered_methods,
                "method_coverage_percent": round(result.metrics.method_coverage_percent, 2),
                "total_branches": result.metrics.total_branches,
                "branch_coverage_percent": round(result.metrics.branch_coverage_percent, 2),
            },
            "summary": {
                "total_gaps": result.total_gaps,
                "total_suggestions": result.total_suggestions,
            },
            "gaps": [
                {
                    "method": gap.method.full_name,
                    "file_path": gap.file_path,
                    "line_number": gap.line_number,
                    "severity": gap.severity.value,
                    "message": gap.message,
                    "details": gap.details,
                }
                for gap in result.gaps
            ],
            "suggestions": [
                {
                    "test_name": sug.test_name,
                    "method": sug.method.full_name,
                    "priority": sug.priority.value,
                    "test_type": sug.test_type,
                    "description": sug.description,
                    "test_cases": sug.test_cases,
                }
                for sug in result.suggestions
            ],
            "class_coverage": [
                {
                    "class_name": cls.class_name,
                    "file_path": cls.file_path,
                    "total_methods": cls.total_methods,
                    "covered_methods": cls.covered_methods,
                    "coverage_percent": round(cls.coverage_percent, 2),
                    "uncovered_methods": cls.uncovered_methods,
                }
                for cls in result.class_coverage
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: CoverageReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall Coverage Analysis Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
        lines.append("")

        # Metrics
        lines.append("## Coverage Metrics")
        lines.append("")
        lines.append(f"- **Method Coverage:** {result.metrics.method_coverage_percent:.1f}%")
        lines.append(f"  - Total Methods: {result.metrics.total_methods}")
        lines.append(f"  - Covered: {result.metrics.covered_methods}")
        if result.metrics.total_branches > 0:
            lines.append(f"- **Branch Coverage:** {result.metrics.branch_coverage_percent:.1f}%")
        lines.append("")

        # Gaps
        if result.gaps:
            lines.append("## Coverage Gaps")
            lines.append("")
            lines.append("| Method | File | Severity | Message |")
            lines.append("|--------|------|----------|---------|")

            for gap in result.gaps[:20]:
                lines.append(
                    f"| {gap.method.full_name} | {gap.file_path}:{gap.line_number} | "
                    f"{gap.severity.value.upper()} | {gap.message} |"
                )

            if len(result.gaps) > 20:
                lines.append(f"| ... | ... | ... | +{len(result.gaps) - 20} more gaps |")

            lines.append("")

        # Suggestions
        if result.suggestions:
            lines.append("## Test Suggestions")
            lines.append("")
            lines.append("| Test | Priority | Type | Description |")
            lines.append("|------|----------|------|-------------|")

            for sug in result.suggestions[:15]:
                lines.append(
                    f"| {sug.test_name} | {sug.priority.value.upper()} | "
                    f"{sug.test_type} | {sug.description} |"
                )

            lines.append("")

        # Class coverage
        if result.class_coverage:
            lines.append("## Class Coverage")
            lines.append("")
            lines.append("| Class | Coverage | Covered/Total | Uncovered Methods |")
            lines.append("|-------|----------|---------------|-------------------|")

            for cls in sorted(result.class_coverage, key=lambda c: c.coverage_percent)[:20]:
                uncovered = ", ".join(cls.uncovered_methods[:3])
                if len(cls.uncovered_methods) > 3:
                    uncovered += f" +{len(cls.uncovered_methods) - 3} more"

                lines.append(
                    f"| {cls.class_name} | {cls.coverage_percent:.1f}% | "
                    f"{cls.covered_methods}/{cls.total_methods} | {uncovered} |"
                )

            lines.append("")

        return "\n".join(lines)

    def quick_check(self, scan_path: Optional[Path] = None) -> dict:
        """
        Perform a quick coverage health check.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict with coverage health metrics
        """
        result = self.analyze(scan_path)

        # Count by severity
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
