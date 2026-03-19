"""
Baseline System Models

Pydantic models for managing baseline violations.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BaselineEntry(BaseModel):
    """Represents a single baselined violation."""
    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., description="Line number of violation")
    violation_type: str = Field(..., description="Type of violation (e.g., 'lazy_import', 'complexity')")
    violation_id: str = Field(..., description="Unique identifier for the violation")
    message: str = Field("", description="Original violation message")
    reason: str = Field("", description="Reason for baselining")
    created_at: datetime = Field(default_factory=datetime.now, description="When entry was created")
    created_by: str = Field("", description="Who created this baseline entry")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")

    class Config:
        use_enum_values = True

    @property
    def is_expired(self) -> bool:
        """Check if this baseline entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def matches(self, file_path: str, line_number: int, violation_type: str) -> bool:
        """
        Check if this entry matches a violation.

        Args:
            file_path: File path to check
            line_number: Line number to check
            violation_type: Type of violation

        Returns:
            True if this entry matches the violation
        """
        return (
            self.file_path == file_path
            and self.line_number == line_number
            and self.violation_type == violation_type
            and not self.is_expired
        )

    def matches_fuzzy(self, file_path: str, violation_type: str, message: str) -> bool:
        """
        Fuzzy match for violations where line numbers may shift.

        Args:
            file_path: File path to check
            violation_type: Type of violation
            message: Violation message to compare

        Returns:
            True if this entry likely matches the violation
        """
        return (
            self.file_path == file_path
            and self.violation_type == violation_type
            and self.message == message
            and not self.is_expired
        )


class BaselineStats(BaseModel):
    """Statistics about baseline entries."""
    total_entries: int = Field(0, description="Total number of baseline entries")
    entries_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by violation type")
    entries_by_file: Dict[str, int] = Field(default_factory=dict, description="Count by file")
    expired_entries: int = Field(0, description="Number of expired entries")
    active_entries: int = Field(0, description="Number of active entries")

    class Config:
        use_enum_values = True


class BaselineFile(BaseModel):
    """
    Complete baseline file structure.

    This is the root model that gets serialized to/from .asgard-baseline.json
    """
    version: str = Field("1.0.0", description="Baseline file format version")
    created_at: datetime = Field(default_factory=datetime.now, description="When baseline was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="When baseline was last updated")
    project_path: str = Field("", description="Root path of the project")
    entries: List[BaselineEntry] = Field(default_factory=list, description="Baseline entries")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True

    def add_entry(self, entry: BaselineEntry) -> None:
        """Add a new baseline entry."""
        self.entries.append(entry)
        self.updated_at = datetime.now()

    def remove_entry(self, violation_id: str) -> bool:
        """
        Remove an entry by violation ID.

        Returns:
            True if entry was found and removed
        """
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.violation_id != violation_id]
        if len(self.entries) < original_count:
            self.updated_at = datetime.now()
            return True
        return False

    def find_match(
        self,
        file_path: str,
        line_number: int,
        violation_type: str,
    ) -> Optional[BaselineEntry]:
        """
        Find a matching baseline entry.

        Args:
            file_path: File path to match
            line_number: Line number to match
            violation_type: Type of violation

        Returns:
            Matching BaselineEntry or None
        """
        for entry in self.entries:
            if entry.matches(file_path, line_number, violation_type):
                return entry
        return None

    def find_fuzzy_match(
        self,
        file_path: str,
        violation_type: str,
        message: str,
    ) -> Optional[BaselineEntry]:
        """
        Find a fuzzy-matching baseline entry.

        Args:
            file_path: File path to match
            violation_type: Type of violation
            message: Violation message

        Returns:
            Matching BaselineEntry or None
        """
        for entry in self.entries:
            if entry.matches_fuzzy(file_path, violation_type, message):
                return entry
        return None

    def get_stats(self) -> BaselineStats:
        """Calculate statistics for this baseline."""
        stats = BaselineStats(total_entries=len(self.entries), expired_entries=0, active_entries=0)

        for entry in self.entries:
            # By type
            stats.entries_by_type[entry.violation_type] = \
                stats.entries_by_type.get(entry.violation_type, 0) + 1

            # By file
            stats.entries_by_file[entry.file_path] = \
                stats.entries_by_file.get(entry.file_path, 0) + 1

            # Expired vs active
            if entry.is_expired:
                stats.expired_entries += 1
            else:
                stats.active_entries += 1

        return stats

    def clean_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if not e.is_expired]
        removed = original_count - len(self.entries)
        if removed > 0:
            self.updated_at = datetime.now()
        return removed
