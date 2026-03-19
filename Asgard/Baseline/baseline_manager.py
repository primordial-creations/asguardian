"""
Baseline Manager

Manages creating, loading, and filtering violations against baseline.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, cast

from Asgard.Baseline.models import (
    BaselineEntry,
    BaselineFile,
    BaselineStats,
)

# Type variable for reports
T = TypeVar('T')


class BaselineManager:
    """
    Manages baseline files for suppressing known violations.

    Usage:
        manager = BaselineManager(project_path)

        # Create baseline from current violations
        manager.create_from_report(lazy_import_report, "lazy_import")

        # Filter violations against baseline
        filtered_violations = manager.filter_violations(
            report.detected_imports,
            violation_type="lazy_import",
        )

        # Show baseline stats
        stats = manager.get_stats()
    """

    DEFAULT_BASELINE_FILE = ".asgard-baseline.json"

    def __init__(
        self,
        project_path: Optional[Path] = None,
        baseline_file: Optional[str] = None,
    ):
        """
        Initialize the baseline manager.

        Args:
            project_path: Root path of the project
            baseline_file: Name of the baseline file (default: .asgard-baseline.json)
        """
        self.project_path = project_path or Path.cwd()
        self.baseline_file = baseline_file or self.DEFAULT_BASELINE_FILE
        self.baseline_path = self.project_path / self.baseline_file
        self._baseline: Optional[BaselineFile] = None

    def load(self) -> BaselineFile:
        """
        Load the baseline file.

        Returns:
            BaselineFile object (creates new if doesn't exist)
        """
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
        """
        Create baseline entries from a list of violations.

        Args:
            violations: List of violation objects with file_path, line_number attributes
            violation_type: Type identifier for these violations
            reason: Reason for baselining
            created_by: Who created this baseline

        Returns:
            Number of entries created
        """
        baseline = self.load()
        count = 0

        for v in violations:
            # Generate unique ID
            file_path = self._relative_path(getattr(v, 'file_path', ''))
            line_number = getattr(v, 'line_number', 0)
            message = self._get_violation_message(v)

            violation_id = self._generate_violation_id(
                file_path, line_number, violation_type, message
            )

            # Check if already baselined
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

        self.save()
        return count

    def filter_violations(
        self,
        violations: List[T],
        violation_type: str,
        use_fuzzy_matching: bool = False,
    ) -> List[T]:
        """
        Filter violations against the baseline.

        Args:
            violations: List of violation objects
            violation_type: Type identifier for these violations
            use_fuzzy_matching: Use fuzzy matching (ignores line number shifts)

        Returns:
            List of violations NOT in baseline (new violations)
        """
        baseline = self.load()
        new_violations = []

        for v in violations:
            file_path = self._relative_path(getattr(v, 'file_path', ''))
            line_number = getattr(v, 'line_number', 0)
            message = self._get_violation_message(v)

            if use_fuzzy_matching:
                match = baseline.find_fuzzy_match(file_path, violation_type, message)
            else:
                match = baseline.find_match(file_path, line_number, violation_type)

            if match is None:
                new_violations.append(v)

        return new_violations

    def get_baselined_count(
        self,
        violations: List[Any],
        violation_type: str,
    ) -> int:
        """
        Count how many violations are baselined.

        Args:
            violations: List of violation objects
            violation_type: Type identifier

        Returns:
            Number of violations that are baselined
        """
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

        Args:
            file_path: Relative path to file
            line_number: Line number of violation
            violation_type: Type of violation
            message: Original violation message
            reason: Reason for baselining
            created_by: Who created this entry

        Returns:
            True if entry was added, False if already exists
        """
        baseline = self.load()

        rel_path = self._relative_path(file_path)
        if baseline.find_match(rel_path, line_number, violation_type):
            return False

        violation_id = self._generate_violation_id(
            rel_path, line_number, violation_type, message
        )

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
        """
        Remove a baseline entry by ID.

        Args:
            violation_id: Unique violation identifier

        Returns:
            True if entry was found and removed
        """
        baseline = self.load()
        result = baseline.remove_entry(violation_id)
        if result:
            self.save()
        return cast(bool, result)

    def clean_expired(self) -> int:
        """
        Remove expired baseline entries.

        Returns:
            Number of entries removed
        """
        baseline = self.load()
        count = baseline.clean_expired()
        if count > 0:
            self.save()
        return cast(int, count)

    def get_stats(self) -> BaselineStats:
        """
        Get statistics about the baseline.

        Returns:
            BaselineStats object
        """
        baseline = self.load()
        return baseline.get_stats()

    def list_entries(
        self,
        violation_type: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> List[BaselineEntry]:
        """
        List baseline entries with optional filtering.

        Args:
            violation_type: Filter by violation type
            file_path: Filter by file path

        Returns:
            List of matching BaselineEntry objects
        """
        baseline = self.load()
        entries = baseline.entries

        if violation_type:
            entries = [e for e in entries if e.violation_type == violation_type]

        if file_path:
            rel_path = self._relative_path(file_path)
            entries = [e for e in entries if e.file_path == rel_path]

        return cast(List[Any], entries)

    def generate_report(self, output_format: str = "text") -> str:
        """
        Generate a report of baseline entries.

        Args:
            output_format: Output format (text, json, markdown)

        Returns:
            Formatted report string
        """
        baseline = self.load()
        stats = baseline.get_stats()

        if output_format == "json":
            return json.dumps(baseline.model_dump(mode='json'), indent=2, default=str)

        elif output_format == "markdown":
            return self._format_markdown_report(baseline, stats)

        else:
            return self._format_text_report(baseline, stats)

    def _relative_path(self, path: str) -> str:
        """Convert absolute path to relative path."""
        try:
            return str(Path(path).relative_to(self.project_path))
        except ValueError:
            return path

    def _get_violation_message(self, violation: Any) -> str:
        """Extract message from violation object."""
        # Try common attribute names
        for attr in ['message', 'description', 'import_statement', 'code_snippet']:
            if hasattr(violation, attr):
                return str(getattr(violation, attr, ''))
        return ""

    def _generate_violation_id(
        self,
        file_path: str,
        line_number: int,
        violation_type: str,
        message: str,
    ) -> str:
        """Generate a unique ID for a violation."""
        content = f"{file_path}:{line_number}:{violation_type}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _format_text_report(self, baseline: BaselineFile, stats: BaselineStats) -> str:
        """Format baseline report as text."""
        lines = [
            "=" * 60,
            "BASELINE REPORT",
            "=" * 60,
            "",
            f"Baseline File: {self.baseline_path}",
            f"Created: {baseline.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Updated: {baseline.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Entries: {stats.total_entries}",
            f"Active: {stats.active_entries}",
            f"Expired: {stats.expired_entries}",
            "",
        ]

        if stats.entries_by_type:
            lines.extend(["By Type:", "-" * 20])
            for vtype, count in sorted(stats.entries_by_type.items()):
                lines.append(f"  {vtype}: {count}")
            lines.append("")

        if stats.entries_by_file:
            lines.extend(["Top Files:", "-" * 20])
            top_files = sorted(stats.entries_by_file.items(), key=lambda x: x[1], reverse=True)[:10]
            for fpath, count in top_files:
                lines.append(f"  {fpath}: {count}")
            lines.append("")

        if baseline.entries:
            lines.extend(["ENTRIES", "-" * 40])
            for entry in baseline.entries[:30]:
                status = "[EXPIRED]" if entry.is_expired else ""
                lines.append(f"  {entry.file_path}:{entry.line_number} [{entry.violation_type}] {status}")
            if len(baseline.entries) > 30:
                lines.append(f"  ... and {len(baseline.entries) - 30} more")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _format_markdown_report(self, baseline: BaselineFile, stats: BaselineStats) -> str:
        """Format baseline report as markdown."""
        lines = [
            "# Baseline Report",
            "",
            f"**Baseline File:** `{self.baseline_path}`",
            f"**Created:** {baseline.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Updated:** {baseline.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Entries | {stats.total_entries} |",
            f"| Active | {stats.active_entries} |",
            f"| Expired | {stats.expired_entries} |",
            "",
        ]

        if stats.entries_by_type:
            lines.extend([
                "## By Type",
                "",
                "| Type | Count |",
                "|------|-------|",
            ])
            for vtype, count in sorted(stats.entries_by_type.items()):
                lines.append(f"| {vtype} | {count} |")
            lines.append("")

        if baseline.entries:
            lines.extend([
                "## Entries",
                "",
                "| File | Line | Type | Status |",
                "|------|------|------|--------|",
            ])
            for entry in baseline.entries[:50]:
                status = "Expired" if entry.is_expired else "Active"
                lines.append(f"| `{entry.file_path}` | {entry.line_number} | {entry.violation_type} | {status} |")

        return "\n".join(lines)
