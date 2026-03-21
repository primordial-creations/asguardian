"""
Baseline Manager

Manages creating, loading, and filtering violations against baseline.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, TypeVar, cast

from Asgard.Baseline._baseline_helpers import generate_violation_id, relative_path
from Asgard.Baseline._baseline_operations import (
    create_from_violations as _create_from_violations,
    filter_violations as _filter_violations,
)
from Asgard.Baseline._baseline_report import format_markdown_report, format_text_report
from Asgard.Baseline.models import (
    BaselineEntry,
    BaselineFile,
    BaselineStats,
)

T = TypeVar('T')


class BaselineManager:
    """
    Manages baseline files for suppressing known violations.

    Usage:
        manager = BaselineManager(project_path)

        # Create baseline from current violations
        manager.create_from_violations(violations, "lazy_import")

        # Filter violations against baseline
        filtered = manager.filter_violations(violations, "lazy_import")

        # Show baseline stats
        stats = manager.get_stats()
    """

    DEFAULT_BASELINE_FILE = ".asgard-baseline.json"

    def __init__(
        self,
        project_path: Optional[Path] = None,
        baseline_file: Optional[str] = None,
    ):
        self.project_path = project_path or Path.cwd()
        self.baseline_file = baseline_file or self.DEFAULT_BASELINE_FILE
        self.baseline_path = self.project_path / self.baseline_file
        self._baseline: Optional[BaselineFile] = None

    def load(self) -> BaselineFile:
        """Load the baseline file."""
        if self._baseline is not None:
            return self._baseline

        if self.baseline_path.exists():
            with open(self.baseline_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._baseline = BaselineFile(**data)
        else:
            self._baseline = BaselineFile(project_path=str(self.project_path))

        return self._baseline

    def save(self) -> None:
        """Save the baseline file to disk."""
        if self._baseline is None:
            return

        self._baseline.updated_at = datetime.now()

        with open(self.baseline_path, 'w', encoding='utf-8') as f:
            json.dump(
                self._baseline.model_dump(mode='json'),
                f,
                indent=2,
                default=str,
            )

    def create_from_violations(
        self,
        violations: List[Any],
        violation_type: str,
        reason: str = "Initial baseline",
        created_by: str = "asgard",
    ) -> int:
        """Create baseline entries from a list of violations."""
        return _create_from_violations(
            violations,
            violation_type,
            self.load(),
            self.project_path,
            self.save,
            reason,
            created_by,
        )

    def filter_violations(
        self,
        violations: List[T],
        violation_type: str,
        use_fuzzy_matching: bool = False,
    ) -> List[T]:
        """Filter violations against the baseline."""
        return _filter_violations(
            violations,
            violation_type,
            self.load(),
            self.project_path,
            use_fuzzy_matching,
        )

    def get_baselined_count(
        self,
        violations: List[Any],
        violation_type: str,
    ) -> int:
        """Count how many violations are baselined."""
        total = len(violations)
        new = len(self.filter_violations(violations, violation_type))
        return total - new

    def add_entry(
        self,
        file_path: str,
        line_number: int,
        violation_type: str,
        message: str = "",
        reason: str = "",
        created_by: str = "asgard",
    ) -> bool:
        """
        Manually add a baseline entry.

        Returns:
            True if entry was added, False if already exists
        """
        baseline = self.load()

        rel_path = relative_path(self.project_path, file_path)
        if baseline.find_match(rel_path, line_number, violation_type):
            return False

        violation_id = generate_violation_id(rel_path, line_number, violation_type, message)

        entry = BaselineEntry(
            file_path=rel_path,
            line_number=line_number,
            violation_type=violation_type,
            violation_id=violation_id,
            message=message,
            reason=reason,
            created_by=created_by,
        )

        baseline.add_entry(entry)
        self.save()
        return True

    def remove_entry(self, violation_id: str) -> bool:
        """Remove a baseline entry by ID."""
        baseline = self.load()
        result = baseline.remove_entry(violation_id)
        if result:
            self.save()
        return cast(bool, result)

    def clean_expired(self) -> int:
        """Remove expired baseline entries."""
        baseline = self.load()
        count = baseline.clean_expired()
        if count > 0:
            self.save()
        return cast(int, count)

    def get_stats(self) -> BaselineStats:
        """Get statistics about the baseline."""
        return self.load().get_stats()

    def list_entries(
        self,
        violation_type: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> List[BaselineEntry]:
        """List baseline entries with optional filtering."""
        baseline = self.load()
        entries = baseline.entries

        if violation_type:
            entries = [e for e in entries if e.violation_type == violation_type]

        if file_path:
            rel_path = relative_path(self.project_path, file_path)
            entries = [e for e in entries if e.file_path == rel_path]

        return cast(List[Any], entries)

    def generate_report(self, output_format: str = "text") -> str:
        """Generate a report of baseline entries."""
        baseline = self.load()
        stats = baseline.get_stats()

        if output_format == "json":
            return json.dumps(baseline.model_dump(mode='json'), indent=2, default=str)

        elif output_format == "markdown":
            return format_markdown_report(baseline, stats, self.baseline_path)

        else:
            return format_text_report(baseline, stats, self.baseline_path)
