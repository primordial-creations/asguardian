"""
Heimdall Architecture Analyzer Service

Unified analyzer that combines all architecture analysis features.
"""

import json
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

    def generate_report(
        self,
        result: ArchitectureReport,
        format: str = "text"
    ) -> str:
        """
        Generate a formatted report.

        Args:
            result: ArchitectureReport to format
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

    def _generate_text_report(self, result: ArchitectureReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL ARCHITECTURE ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:        {result.scan_path}")
        lines.append(f"  Scanned At:       {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Duration:         {result.scan_duration_seconds:.2f}s")
        lines.append("")
        lines.append(f"  Total Violations: {result.total_violations}")
        lines.append(f"  Patterns Found:   {result.total_patterns}")
        lines.append(f"  Health Status:    {'HEALTHY' if result.is_healthy else 'NEEDS ATTENTION'}")
        lines.append("")

        # SOLID summary
        if result.solid_report:
            lines.append("-" * 70)
            lines.append("  SOLID PRINCIPLES")
            lines.append("-" * 70)
            lines.append("")
            lines.append(
                "  Checks five object-oriented design principles: Single Responsibility"
                " (one reason to change), Open/Closed (open for extension, closed for"
                " modification), Liskov Substitution (subtypes behave like their base),"
                " Interface Segregation (no fat interfaces), Dependency Inversion (depend"
                " on abstractions)."
            )
            lines.append("")
            lines.append(f"  Classes Analyzed:  {result.solid_report.total_classes}")
            lines.append(f"  Violations Found:  {result.solid_report.total_violations}")
            lines.append("")

            for principle, violations in result.solid_report.violations_by_principle.items():
                if violations:
                    lines.append(f"  {violations[0].principle_name}: {len(violations)} violations")

            lines.append("")

        # Layer summary
        if result.layer_report:
            lines.append("-" * 70)
            lines.append("  LAYER ARCHITECTURE")
            lines.append("-" * 70)
            lines.append("")
            lines.append(
                "  Verifies that code only imports across layers in the permitted direction"
                " (e.g. presentation -> service -> repository -> domain). A violation means"
                " a lower layer is importing from a higher one."
            )
            lines.append("")
            lines.append(f"  Layers Defined:    {len(result.layer_report.layers)}")
            lines.append(f"  Violations Found:  {result.layer_report.total_violations}")
            lines.append(f"  Status:            {'VALID' if result.layer_report.is_valid else 'INVALID'}")
            lines.append("")

        # Pattern summary
        if result.pattern_report:
            lines.append("-" * 70)
            lines.append("  DESIGN PATTERNS")
            lines.append("-" * 70)
            lines.append("")
            lines.append(
                "  Identifies common GoF structural and behavioural patterns (Factory,"
                " Singleton, Observer, Strategy, etc.) present in the codebase."
            )
            lines.append("")
            lines.append(f"  Patterns Found:    {result.pattern_report.total_patterns}")
            lines.append("")

            for pattern_type, matches in result.pattern_report.patterns_by_type.items():
                if matches:
                    lines.append(f"  {pattern_type.value.replace('_', ' ').title()}: {len(matches)}")

            lines.append("")

        # Hexagonal summary
        if result.hexagonal_report:
            lines.append("-" * 70)
            lines.append("  HEXAGONAL ARCHITECTURE")
            lines.append("-" * 70)
            lines.append("")
            lines.append(
                "  Checks that domain logic is isolated from infrastructure by ports"
                " (interfaces) and adapters (implementations). A violation means domain"
                " code directly depends on an adapter."
            )
            lines.append("")
            lines.append(f"  Ports Found:       {len(result.hexagonal_report.ports)}")
            lines.append(f"  Adapters Found:    {len(result.hexagonal_report.adapters)}")
            lines.append(f"  Violations Found:  {result.hexagonal_report.total_violations}")
            lines.append(f"  Status:            {'VALID' if result.hexagonal_report.is_valid else 'INVALID'}")
            lines.append("")

        # Pattern candidate suggestions summary
        if result.suggestion_report:
            lines.append("-" * 70)
            lines.append("  PATTERN CANDIDATE SUGGESTIONS")
            lines.append("-" * 70)
            lines.append("")
            lines.append(
                "  Analyses code smells and structural signals to suggest GoF design"
                " patterns that could improve the design (Builder, Strategy, Observer, etc.)."
                " These are candidates — not violations."
            )
            lines.append("")
            lines.append(f"  Suggestions Found: {result.suggestion_report.total_suggestions}")
            lines.append("")
            for pattern_type, suggestions in result.suggestion_report.suggestions_by_pattern.items():
                if suggestions:
                    label = pattern_type.value.replace("_", " ").title()
                    lines.append(f"  {label}: {len(suggestions)} candidate(s)")
            lines.append("")

        # Recommendations
        lines.append("-" * 70)
        lines.append("  RECOMMENDATIONS")
        lines.append("-" * 70)
        lines.append("")

        recommendations = self._generate_recommendations(result)
        for rec in recommendations:
            lines.append(f"  - {rec}")
        lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: ArchitectureReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "scan_duration_seconds": result.scan_duration_seconds,
            "summary": {
                "total_violations": result.total_violations,
                "total_patterns": result.total_patterns,
                "is_healthy": result.is_healthy,
            },
        }

        if result.solid_report:
            output["solid"] = {
                "total_classes": result.solid_report.total_classes,
                "total_violations": result.solid_report.total_violations,
                "violations": [
                    {
                        "principle": v.principle.value,
                        "class_name": v.class_name,
                        "file_path": v.file_path,
                        "line_number": v.line_number,
                        "message": v.message,
                        "severity": v.severity.value,
                    }
                    for v in result.solid_report.violations
                ],
            }

        if result.layer_report:
            output["layers"] = {
                "is_valid": result.layer_report.is_valid,
                "total_violations": result.layer_report.total_violations,
                "layers": [
                    {
                        "name": l.name,
                        "patterns": l.patterns,
                        "allowed_dependencies": l.allowed_dependencies,
                    }
                    for l in result.layer_report.layers
                ],
                "violations": [
                    {
                        "source_module": v.source_module,
                        "source_layer": v.source_layer,
                        "target_module": v.target_module,
                        "target_layer": v.target_layer,
                        "message": v.message,
                    }
                    for v in result.layer_report.violations
                ],
            }

        if result.pattern_report:
            output["patterns"] = {
                "total_patterns": result.pattern_report.total_patterns,
                "patterns": [
                    {
                        "pattern_type": p.pattern_type.value,
                        "class_name": p.class_name,
                        "file_path": p.file_path,
                        "confidence": p.confidence,
                    }
                    for p in result.pattern_report.patterns
                ],
            }

        if result.hexagonal_report:
            output["hexagonal"] = {
                "is_valid": result.hexagonal_report.is_valid,
                "total_violations": result.hexagonal_report.total_violations,
                "ports": [
                    {
                        "name": p.name,
                        "direction": p.direction.value,
                        "abstract_methods": p.abstract_methods,
                    }
                    for p in result.hexagonal_report.ports
                ],
                "adapters": [
                    {
                        "name": a.name,
                        "implements_port": a.implements_port,
                        "zone": a.zone.value,
                    }
                    for a in result.hexagonal_report.adapters
                ],
                "violations": [
                    {
                        "source_zone": v.source_zone.value,
                        "target_zone": v.target_zone.value,
                        "message": v.message,
                        "severity": v.severity.value,
                    }
                    for v in result.hexagonal_report.violations
                ],
            }

        if result.suggestion_report:
            output["pattern_suggestions"] = {
                "total_suggestions": result.suggestion_report.total_suggestions,
                "suggestions": [
                    {
                        "pattern_type": s.pattern_type.value,
                        "class_name": s.class_name,
                        "file_path": s.file_path,
                        "line_number": s.line_number,
                        "confidence": s.confidence,
                        "rationale": s.rationale,
                        "signals": s.signals,
                        "benefit": s.benefit,
                    }
                    for s in result.suggestion_report.suggestions
                ],
            }

        output["recommendations"] = self._generate_recommendations(result)

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: ArchitectureReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall Architecture Analysis Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Violations:** {result.total_violations}")
        lines.append(f"- **Patterns Found:** {result.total_patterns}")
        lines.append(f"- **Health Status:** {'Healthy' if result.is_healthy else 'Needs Attention'}")
        lines.append("")

        # SOLID section
        if result.solid_report:
            lines.append("## SOLID Principles")
            lines.append("")
            lines.append(f"- **Classes Analyzed:** {result.solid_report.total_classes}")
            lines.append(f"- **Violations Found:** {result.solid_report.total_violations}")
            lines.append("")

            if result.solid_report.violations:
                lines.append("### Violations")
                lines.append("")
                lines.append("| Principle | Class | Message | Severity |")
                lines.append("|-----------|-------|---------|----------|")

                for v in result.solid_report.violations:
                    lines.append(
                        f"| {v.principle_name[:20]} | {v.class_name} | "
                        f"{v.message[:40]} | {v.severity.value.upper()} |"
                    )

                lines.append("")

        # Layer section
        if result.layer_report:
            lines.append("## Layer Architecture")
            lines.append("")
            lines.append(f"- **Status:** {'Valid' if result.layer_report.is_valid else 'Invalid'}")
            lines.append(f"- **Violations:** {result.layer_report.total_violations}")
            lines.append("")

            if result.layer_report.violations:
                lines.append("### Layer Violations")
                lines.append("")
                lines.append("| Source | Target | Message |")
                lines.append("|--------|--------|---------|")

                for v in result.layer_report.violations:
                    lines.append(
                        f"| {v.source_module} ({v.source_layer}) | "
                        f"{v.target_module} ({v.target_layer}) | {v.message} |"
                    )

                lines.append("")

        # Pattern section
        if result.pattern_report and result.pattern_report.patterns:
            lines.append("## Design Patterns")
            lines.append("")
            lines.append("| Pattern | Class | Confidence |")
            lines.append("|---------|-------|------------|")

            for p in result.pattern_report.patterns:
                lines.append(
                    f"| {p.pattern_type.value.replace('_', ' ').title()} | "
                    f"{p.class_name} | {p.confidence:.0%} |"
                )

            lines.append("")

        # Hexagonal section
        if result.hexagonal_report:
            lines.append("## Hexagonal Architecture")
            lines.append("")
            lines.append(f"- **Status:** {'Valid' if result.hexagonal_report.is_valid else 'Invalid'}")
            lines.append(f"- **Ports:** {len(result.hexagonal_report.ports)}")
            lines.append(f"- **Adapters:** {len(result.hexagonal_report.adapters)}")
            lines.append(f"- **Violations:** {result.hexagonal_report.total_violations}")
            lines.append("")

            if result.hexagonal_report.violations:
                lines.append("### Hexagonal Violations")
                lines.append("")
                lines.append("| Severity | Source Zone | Target Zone | Message |")
                lines.append("|----------|------------|-------------|---------|")

                for v in result.hexagonal_report.violations:
                    lines.append(
                        f"| {v.severity.value.upper()} | "
                        f"{v.source_zone.value} | {v.target_zone.value} | "
                        f"{v.message[:60]} |"
                    )

                lines.append("")

        # Pattern candidate suggestions section
        if result.suggestion_report and result.suggestion_report.suggestions:
            lines.append("## Pattern Candidate Suggestions")
            lines.append("")
            lines.append(f"- **Total Suggestions:** {result.suggestion_report.total_suggestions}")
            lines.append("")
            lines.append("| Pattern | Class | Confidence | Signals |")
            lines.append("|---------|-------|------------|---------|")

            for s in result.suggestion_report.suggestions:
                signal_str = "; ".join(s.signals[:2]) if s.signals else ""
                lines.append(
                    f"| {s.pattern_type.value.replace('_', ' ').title()} | "
                    f"{s.class_name} | {s.confidence:.0%} | {signal_str[:60]} |"
                )

            lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")

        for rec in self._generate_recommendations(result):
            lines.append(f"- {rec}")

        lines.append("")

        return "\n".join(lines)

    def _generate_recommendations(self, result: ArchitectureReport) -> list:
        """Generate recommendations based on analysis."""
        recommendations = []

        if result.solid_report:
            by_principle = result.solid_report.violations_by_principle

            if len(by_principle.get(by_principle.__class__.__mro__[0], [])) > 5:
                pass  # Skip for now

            for principle, violations in by_principle.items():
                if len(violations) > 3:
                    recommendations.append(
                        f"Address {len(violations)} {violations[0].principle_name} violations"
                    )

        if result.layer_report:
            if not result.layer_report.is_valid:
                recommendations.append(
                    f"Fix {result.layer_report.total_violations} layer architecture violations"
                )

        if result.pattern_report:
            if result.pattern_report.total_patterns == 0:
                recommendations.append(
                    "Consider using design patterns for common scenarios"
                )

        if result.hexagonal_report:
            if not result.hexagonal_report.is_valid:
                recommendations.append(
                    f"Fix {result.hexagonal_report.total_violations} hexagonal architecture violations"
                )
            if not result.hexagonal_report.ports:
                recommendations.append(
                    "No ports detected -- define abstract base classes for domain boundaries"
                )

        if result.suggestion_report and result.suggestion_report.total_suggestions > 0:
            recommendations.append(
                f"Review {result.suggestion_report.total_suggestions} pattern candidate suggestion(s)"
                " -- applying these patterns could improve maintainability and extensibility"
            )

        if not recommendations:
            recommendations.append("Architecture is in good shape!")

        return recommendations

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
