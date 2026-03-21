"""
Heimdall Maintainability Analyzer - recommendation generation helpers.

Standalone functions for generating per-function and project-wide
improvement recommendations. Accept data values as explicit parameters.
"""

from typing import List

from Asgard.Heimdall.Quality.models.maintainability_models import MaintainabilityReport


def generate_recommendations(
    index: float,
    complexity: int,
    loc: int,
    volume: float,
    comment_pct: float,
) -> List[str]:
    """Generate specific recommendations for improvement."""
    recommendations = []

    if index < 25:
        recommendations.append("CRITICAL: Major refactoring required - consider rewriting")
    elif index < 50:
        recommendations.append("Significant improvement needed - plan refactoring effort")
    elif index < 70:
        recommendations.append("Some improvements recommended for long-term maintainability")

    if complexity > 15:
        recommendations.append(f"Reduce cyclomatic complexity ({complexity} > 15): extract helper functions")

    if complexity > 25:
        recommendations.append(f"Very high complexity ({complexity}): break into smaller units")

    if loc > 50:
        recommendations.append(f"Consider breaking down large function ({loc} lines)")

    if loc > 100:
        recommendations.append(f"Function too long ({loc} lines): extract logical sections")

    if comment_pct < 10:
        recommendations.append("Add documentation: docstrings and inline comments")

    if comment_pct < 5:
        recommendations.append("Minimal documentation - add comprehensive docstrings")

    if volume > 1000:
        recommendations.append("High Halstead volume: simplify algorithms, reduce operator density")

    if volume > 2000:
        recommendations.append("Very high volume: significant algorithm simplification needed")

    return recommendations


def generate_improvement_priorities(report: MaintainabilityReport) -> List[str]:
    """Generate project-wide improvement priorities."""
    priorities = []

    critical_count = report.critical_count
    if critical_count > 0:
        priorities.append(f"URGENT: {critical_count} files with critical maintainability")

    poor_count = report.poor_count
    if poor_count > 0:
        priorities.append(f"Address {poor_count} poorly maintainable files")

    all_functions = []
    for file_result in report.file_results:
        all_functions.extend(file_result.functions)

    common_issues = {
        'high_complexity': sum(1 for f in all_functions if f.cyclomatic_complexity > 15),
        'very_high_complexity': sum(1 for f in all_functions if f.cyclomatic_complexity > 25),
        'long_functions': sum(1 for f in all_functions if f.lines_of_code > 50),
        'very_long_functions': sum(1 for f in all_functions if f.lines_of_code > 100),
        'poor_documentation': sum(1 for f in all_functions if f.comment_percentage < 10),
    }

    if common_issues['very_high_complexity'] > 0:
        priorities.append(f"Critical: {common_issues['very_high_complexity']} functions with complexity > 25")

    if common_issues['high_complexity'] > 10:
        priorities.append(f"High complexity: {common_issues['high_complexity']} functions need refactoring")

    if common_issues['very_long_functions'] > 0:
        priorities.append(f"Very long functions: {common_issues['very_long_functions']} exceed 100 lines")

    if common_issues['long_functions'] > 10:
        priorities.append(f"Long functions: {common_issues['long_functions']} exceed 50 lines")

    if common_issues['poor_documentation'] > 20:
        priorities.append(f"Documentation debt: {common_issues['poor_documentation']} underdocumented functions")

    if report.overall_index >= 85:
        priorities.append("Excellent maintainability - maintain current standards")
    elif report.overall_index >= 70:
        priorities.append("Good maintainability - focus on targeted improvements")
    elif report.overall_index >= 50:
        priorities.append("Moderate maintainability - allocate resources for improvement")
    else:
        priorities.append("Poor overall maintainability - prioritize major refactoring")

    return priorities
