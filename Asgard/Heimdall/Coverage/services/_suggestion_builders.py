"""
Heimdall Suggestion Engine - Builder Helpers

Standalone functions for building test suggestion content: priority calculation,
test name generation, type determination, description/case/rationale generation,
and test skeleton code generation.
"""

from typing import List

from Asgard.Heimdall.Coverage.models.coverage_models import (
    CoverageGap,
    CoverageSeverity,
    MethodInfo,
    MethodType,
    SuggestionPriority,
    TestSuggestion,
)


def calculate_priority(method: MethodInfo, gap: CoverageGap) -> SuggestionPriority:
    """Calculate suggestion priority based on gap severity."""
    if gap.severity == CoverageSeverity.CRITICAL:
        return SuggestionPriority.URGENT
    elif gap.severity == CoverageSeverity.HIGH:
        return SuggestionPriority.HIGH
    elif gap.severity == CoverageSeverity.MODERATE:
        return SuggestionPriority.MEDIUM
    else:
        return SuggestionPriority.LOW


def generate_test_name(method: MethodInfo) -> str:
    """Generate a test function name."""
    if method.class_name:
        return f"test_{method.class_name.lower()}_{method.name}"
    return f"test_{method.name}"


def determine_test_type(method: MethodInfo) -> str:
    """Determine the type of test needed."""
    if method.is_async:
        return "async_unit_test"
    elif method.method_type == MethodType.PROPERTY:
        return "property_test"
    elif method.method_type == MethodType.CLASSMETHOD:
        return "classmethod_test"
    elif method.method_type == MethodType.STATICMETHOD:
        return "staticmethod_test"
    elif method.has_branches and method.branch_count > 3:
        return "parametrized_test"
    else:
        return "unit_test"


def generate_description(method: MethodInfo) -> str:
    """Generate a description for the test."""
    parts = []

    if method.is_async:
        parts.append("async")

    if method.method_type == MethodType.PROPERTY:
        parts.append("property")
    elif method.method_type == MethodType.CLASSMETHOD:
        parts.append("class method")
    elif method.method_type == MethodType.STATICMETHOD:
        parts.append("static method")
    else:
        parts.append("method")

    type_str = " ".join(parts)

    if method.class_name:
        return f"Test the {type_str} '{method.name}' in {method.class_name}"
    return f"Test the {type_str} '{method.name}'"


def generate_test_cases(method: MethodInfo) -> List[str]:
    """Generate suggested test cases."""
    cases = []

    cases.append(f"Test {method.name} with valid input")

    if method.parameter_count > 0:
        cases.append(f"Test {method.name} with invalid parameters")
        if method.parameter_count > 1:
            cases.append(f"Test {method.name} with partial parameters")

    if method.has_branches:
        if method.branch_count <= 3:
            for i in range(method.branch_count):
                cases.append(f"Test {method.name} branch {i + 1}")
        else:
            cases.append(f"Test {method.name} true path")
            cases.append(f"Test {method.name} false path")
            cases.append(f"Test {method.name} edge cases")

    cases.append(f"Test {method.name} error handling")

    if method.is_async:
        cases.append(f"Test {method.name} cancellation")
        cases.append(f"Test {method.name} timeout behavior")

    return cases


def generate_rationale(method: MethodInfo, gap: CoverageGap) -> str:
    """Generate rationale for the test suggestion."""
    reasons = []

    if gap.severity == CoverageSeverity.CRITICAL:
        reasons.append("Critical untested code path")
    elif gap.severity == CoverageSeverity.HIGH:
        reasons.append("High-risk untested code")

    if method.complexity > 5:
        reasons.append(f"High complexity ({method.complexity})")

    if method.has_branches:
        reasons.append(f"Multiple branches ({method.branch_count})")

    if method.is_async:
        reasons.append("Async code needs special test handling")

    if method.method_type == MethodType.PUBLIC:
        reasons.append("Public API method")

    return "; ".join(reasons) if reasons else "Standard test coverage"


def create_suggestion(method: MethodInfo, gap: CoverageGap) -> TestSuggestion:
    """Create a test suggestion for a method."""
    priority = calculate_priority(method, gap)
    test_name = generate_test_name(method)
    test_type = determine_test_type(method)
    description = generate_description(method)
    test_cases = generate_test_cases(method)
    rationale = generate_rationale(method, gap)

    return TestSuggestion(
        method=method,
        test_name=test_name,
        test_type=test_type,
        priority=priority,
        description=description,
        test_cases=test_cases,
        rationale=rationale,
    )


def generate_test_skeleton(suggestion: TestSuggestion) -> str:
    """
    Generate a test code skeleton.

    Args:
        suggestion: Test suggestion

    Returns:
        Python test code skeleton
    """
    method = suggestion.method
    lines = []

    if method.is_async:
        lines.append("import pytest")
        lines.append("")

    if method.is_async:
        lines.append("@pytest.mark.asyncio")
        lines.append(f"async def {suggestion.test_name}():")
    else:
        lines.append(f"def {suggestion.test_name}():")

    lines.append(f'    """{suggestion.description}."""')

    lines.append("    # Arrange")
    if method.class_name:
        lines.append(f"    instance = {method.class_name}()")
    lines.append("")

    lines.append("    # Act")
    if method.class_name:
        if method.is_async:
            lines.append(f"    result = await instance.{method.name}()")
        else:
            lines.append(f"    result = instance.{method.name}()")
    else:
        if method.is_async:
            lines.append(f"    result = await {method.name}()")
        else:
            lines.append(f"    result = {method.name}()")
    lines.append("")

    lines.append("    # Assert")
    lines.append("    assert result is not None  # TODO: Add specific assertions")
    lines.append("")

    return "\n".join(lines)


def generate_parametrized_test(suggestion: TestSuggestion) -> str:
    """
    Generate a parametrized test skeleton.

    Args:
        suggestion: Test suggestion

    Returns:
        Python parametrized test code
    """
    method = suggestion.method
    lines = []

    lines.append("import pytest")
    lines.append("")
    lines.append("")

    lines.append("@pytest.mark.parametrize('input_value,expected', [")
    lines.append("    (None, None),  # TODO: Add test cases")
    lines.append("    ('valid', 'expected_result'),")
    lines.append("    ('edge_case', 'edge_result'),")
    lines.append("])")

    if method.is_async:
        lines.append("@pytest.mark.asyncio")
        lines.append(f"async def {suggestion.test_name}(input_value, expected):")
    else:
        lines.append(f"def {suggestion.test_name}(input_value, expected):")

    lines.append(f'    """{suggestion.description}."""')

    lines.append("    # Arrange")
    if method.class_name:
        lines.append(f"    instance = {method.class_name}()")
    lines.append("")

    lines.append("    # Act")
    if method.class_name:
        if method.is_async:
            lines.append(f"    result = await instance.{method.name}(input_value)")
        else:
            lines.append(f"    result = instance.{method.name}(input_value)")
    else:
        if method.is_async:
            lines.append(f"    result = await {method.name}(input_value)")
        else:
            lines.append(f"    result = {method.name}(input_value)")
    lines.append("")

    lines.append("    # Assert")
    lines.append("    assert result == expected")
    lines.append("")

    return "\n".join(lines)
