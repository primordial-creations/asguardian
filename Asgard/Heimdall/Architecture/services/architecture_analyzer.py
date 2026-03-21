"""
Heimdall Architecture Analyzer Service

Unified analyzer that combines all architecture analysis features.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    ArchitectureReport,
    HexagonalReport,
    LayerDefinition,
    LayerReport,
    PatternReport,
    PatternSuggestionReport,
    SOLIDReport,
)
from Asgard.Heimdall.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Heimdall.Architecture.services.layer_analyzer import LayerAnalyzer
from Asgard.Heimdall.Architecture.services.pattern_detector import PatternDetector
from Asgard.Heimdall.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Heimdall.Architecture.services.pattern_suggester import PatternSuggester
from Asgard.Heimdall.Architecture.services._arch_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
    generate_recommendations as _gen_recommendations,
)


class ArchitectureAnalyzer:
    """
    Unified architecture analyzer combining all analysis features.

    Provides comprehensive architecture analysis including:
    - SOLID principle validation
    - Layer architecture compliance
    - Design pattern detection
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the architecture analyzer."""
        self.config = config or ArchitectureConfig()

        # Initialize sub-analyzers
        self.solid_validator = SOLIDValidator(self.config)
        self.layer_analyzer = LayerAnalyzer(self.config)
        self.pattern_detector = PatternDetector(self.config)
        self.hexagonal_analyzer = HexagonalAnalyzer(self.config)
        self.pattern_suggester = PatternSuggester(self.config)

    def analyze(
        self,
        scan_path: Optional[Path] = None,
        validate_solid: bool = True,
        analyze_layers: bool = True,
        detect_patterns: bool = True,
        analyze_hexagonal: bool = False,
        suggest_patterns: bool = True,
    ) -> ArchitectureReport:
        """
        Perform complete architecture analysis.

        Args:
            scan_path: Root path to scan
            validate_solid: Whether to validate SOLID principles
            analyze_layers: Whether to analyze layer compliance
            detect_patterns: Whether to detect design patterns

        Returns:
            ArchitectureReport with all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = ArchitectureReport(scan_path=str(path))

        # Run enabled analyses
        if validate_solid:
            report.solid_report = self.solid_validator.validate(path)

        if analyze_layers:
            report.layer_report = self.layer_analyzer.analyze(path)

        if detect_patterns:
            report.pattern_report = self.pattern_detector.detect(path)

        if analyze_hexagonal:
            report.hexagonal_report = self.hexagonal_analyzer.analyze(path)

        if suggest_patterns:
            report.suggestion_report = self.pattern_suggester.suggest(path)

        report.scan_duration_seconds = time.time() - start_time

        return report

    def validate_solid(
        self,
        scan_path: Optional[Path] = None
    ) -> SOLIDReport:
        """
        Validate SOLID principles only.

        Args:
            scan_path: Root path to scan

        Returns:
            SOLIDReport with violations
        """
        return self.solid_validator.validate(scan_path)

    def analyze_layers(
        self,
        scan_path: Optional[Path] = None,
        custom_layers: Optional[list] = None
    ) -> LayerReport:
        """
        Analyze layer architecture only.

        Args:
            scan_path: Root path to scan
            custom_layers: Optional custom layer definitions

        Returns:
            LayerReport with violations
        """
        if custom_layers:
            self.layer_analyzer.set_layers(custom_layers)

        return self.layer_analyzer.analyze(scan_path)

    def analyze_hexagonal(
        self,
        scan_path: Optional[Path] = None
    ) -> HexagonalReport:
        """
        Analyze hexagonal architecture only.

        Args:
            scan_path: Root path to scan

        Returns:
            HexagonalReport with violations, ports, and adapters
        """
        return self.hexagonal_analyzer.analyze(scan_path)

    def detect_patterns(
        self,
        scan_path: Optional[Path] = None
    ) -> PatternReport:
        """
        Detect design patterns only.

        Args:
            scan_path: Root path to scan

        Returns:
            PatternReport with detected patterns
        """
        return self.pattern_detector.detect(scan_path)

    def generate_report(self, result: ArchitectureReport, format: str = "text") -> str:
        """Generate a formatted report."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)

    def _generate_recommendations(self, result: ArchitectureReport) -> list:
        """Generate recommendations based on analysis."""
        return _gen_recommendations(result)

    def suggest_patterns(
        self, scan_path: Optional[Path] = None
    ) -> PatternSuggestionReport:
        """
        Analyse the codebase for pattern candidates only.

        Args:
            scan_path: Root path to scan.

        Returns:
            PatternSuggestionReport with all suggestions.
        """
        return self.pattern_suggester.suggest(scan_path)

    def quick_check(self, scan_path: Optional[Path] = None) -> dict:
        """
        Perform a quick architecture health check.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict with health metrics
        """
        result = self.analyze(scan_path)

        return {
            "is_healthy": result.is_healthy,
            "solid_violations": result.solid_report.total_violations if result.solid_report else 0,
            "layer_violations": result.layer_report.total_violations if result.layer_report else 0,
            "patterns_found": result.pattern_report.total_patterns if result.pattern_report else 0,
            "pattern_suggestions": result.suggestion_report.total_suggestions if result.suggestion_report else 0,
            "recommendations": self._generate_recommendations(result),
        }
