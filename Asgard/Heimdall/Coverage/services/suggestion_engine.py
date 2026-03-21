"""
Heimdall Suggestion Engine Service

Generates test suggestions for uncovered code.
"""

from typing import List, Optional

from Asgard.Heimdall.Coverage.models.coverage_models import (
    CoverageConfig,
    CoverageGap,
    CoverageSeverity,
    MethodInfo,
    SuggestionPriority,
    TestSuggestion,
)
from Asgard.Heimdall.Coverage.services._suggestion_builders import (
    create_suggestion,
    generate_parametrized_test,
    generate_test_skeleton,
)


class SuggestionEngine:
    """
    Generates test suggestions for uncovered code.

    Creates targeted test suggestions based on:
    - Method characteristics
    - Code complexity
    - Parameter types
    - Common patterns
    """

    def __init__(self, config: Optional[CoverageConfig] = None):
        """Initialize the suggestion engine."""
        self.config = config or CoverageConfig()

    def generate_suggestions(
        self,
        gaps: List[CoverageGap]
    ) -> List[TestSuggestion]:
        """
        Generate test suggestions for coverage gaps.

        Args:
            gaps: List of coverage gaps

        Returns:
            List of test suggestions
        """
        suggestions = []

        for gap in gaps:
            method = gap.method
            suggestion = create_suggestion(method, gap)
            suggestions.append(suggestion)

        priority_order = {
            SuggestionPriority.URGENT: 0,
            SuggestionPriority.HIGH: 1,
            SuggestionPriority.MEDIUM: 2,
            SuggestionPriority.LOW: 3,
        }
        suggestions.sort(key=lambda s: priority_order[s.priority])

        return suggestions

    def suggest_for_method(self, method: MethodInfo) -> TestSuggestion:
        """
        Generate a test suggestion for a single method.

        Args:
            method: Method to suggest tests for

        Returns:
            TestSuggestion for the method
        """
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.MODERATE,
            message=f"No test for {method.full_name}",
        )

        return create_suggestion(method, gap)

    def generate_test_skeleton(
        self,
        suggestion: TestSuggestion
    ) -> str:
        """
        Generate a test code skeleton.

        Args:
            suggestion: Test suggestion

        Returns:
            Python test code skeleton
        """
        return generate_test_skeleton(suggestion)

    def generate_parametrized_test(
        self,
        suggestion: TestSuggestion
    ) -> str:
        """
        Generate a parametrized test skeleton.

        Args:
            suggestion: Test suggestion

        Returns:
            Python parametrized test code
        """
        return generate_parametrized_test(suggestion)

    def prioritize_suggestions(
        self,
        suggestions: List[TestSuggestion],
        max_count: int = 10
    ) -> List[TestSuggestion]:
        """
        Get the highest priority suggestions.

        Args:
            suggestions: All suggestions
            max_count: Maximum number to return

        Returns:
            Top priority suggestions
        """
        return suggestions[:max_count]
