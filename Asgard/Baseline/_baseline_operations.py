"""
Baseline Manager - Core Operations

Bulk violation processing operations: create_from_violations and filter_violations.
These are extracted from BaselineManager to keep that class under 300 lines.
"""

from pathlib import Path
from typing import Any, Callable, List, Optional, TypeVar

from Asgard.Baseline._baseline_helpers import (
    generate_violation_id,
    get_violation_message,
    relative_path,
)
from Asgard.Baseline.models import BaselineEntry, BaselineFile

T = TypeVar('T')


def create_from_violations(
    violations: List[Any],
    violation_type: str,
    baseline: BaselineFile,
    project_path: Path,
    save_func: Callable[[], None],
    reason: str = "Initial baseline",
    created_by: str = "asgard",
) -> int:
    """
    Create baseline entries from a list of violations.

    Args:
        violations: List of violation objects with file_path, line_number attributes
        violation_type: Type identifier for these violations
        baseline: Loaded BaselineFile to add entries to
        project_path: Project root for relative path computation
        save_func: Callable to persist the baseline after modification
        reason: Reason for baselining
        created_by: Who created this baseline

    Returns:
        Number of entries created
    """
    count = 0

    for v in violations:
        file_path = relative_path(project_path, getattr(v, 'file_path', ''))
        line_number = getattr(v, 'line_number', 0)
        message = get_violation_message(v)

        violation_id = generate_violation_id(file_path, line_number, violation_type, message)

        if baseline.find_match(file_path, line_number, violation_type):
            continue

        entry = BaselineEntry(
            file_path=file_path,
            line_number=line_number,
            violation_type=violation_type,
            violation_id=violation_id,
            message=message,
            reason=reason,
            created_by=created_by,
        )

        baseline.add_entry(entry)
        count += 1

    save_func()
    return count


def filter_violations(
    violations: List[T],
    violation_type: str,
    baseline: BaselineFile,
    project_path: Path,
    use_fuzzy_matching: bool = False,
) -> List[T]:
    """
    Filter violations against the baseline.

    Args:
        violations: List of violation objects
        violation_type: Type identifier for these violations
        baseline: Loaded BaselineFile to filter against
        project_path: Project root for relative path computation
        use_fuzzy_matching: Use fuzzy matching (ignores line number shifts)

    Returns:
        List of violations NOT in baseline (new violations)
    """
    new_violations = []

    for v in violations:
        file_path = relative_path(project_path, getattr(v, 'file_path', ''))
        line_number = getattr(v, 'line_number', 0)
        message = get_violation_message(v)

        if use_fuzzy_matching:
            match: Optional[BaselineEntry] = baseline.find_fuzzy_match(
                file_path, violation_type, message
            )
        else:
            match = baseline.find_match(file_path, line_number, violation_type)

        if match is None:
            new_violations.append(v)

    return new_violations
