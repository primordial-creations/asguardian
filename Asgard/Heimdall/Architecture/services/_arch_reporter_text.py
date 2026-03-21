"""
Heimdall Architecture Analyzer - plain text report generation.
"""

from typing import List

from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureReport


def generate_recommendations(result: ArchitectureReport) -> List[str]:
    """Generate recommendations based on analysis."""
    recommendations = []

    if result.solid_report:
        by_principle = result.solid_report.violations_by_principle
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


def generate_text_report(result: ArchitectureReport) -> str:
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

    if result.suggestion_report:
        lines.append("-" * 70)
        lines.append("  PATTERN CANDIDATE SUGGESTIONS")
        lines.append("-" * 70)
        lines.append("")
        lines.append(
            "  Analyses code smells and structural signals to suggest GoF design"
            " patterns that could improve the design (Builder, Strategy, Observer, etc.)."
            " These are candidates -- not violations."
        )
        lines.append("")
        lines.append(f"  Suggestions Found: {result.suggestion_report.total_suggestions}")
        lines.append("")
        for pattern_type, suggestions in result.suggestion_report.suggestions_by_pattern.items():
            if suggestions:
                label = pattern_type.value.replace("_", " ").title()
                lines.append(f"  {label}: {len(suggestions)} candidate(s)")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  RECOMMENDATIONS")
    lines.append("-" * 70)
    lines.append("")
    for rec in generate_recommendations(result):
        lines.append(f"  - {rec}")
    lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
