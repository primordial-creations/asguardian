"""
Baseline System Models

Pydantic models for managing baseline violations.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Baseline._baseline_helpers import (
    hash_violation_message,
    messages_match,
)


class BaselineEntry(BaseModel):
    """Represents a single baselined violation."""
    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., description="Line number of violation")
    violation_type: str = Field(..., description="Type of violation (e.g., 'lazy_import', 'complexity')")
    violation_id: str = Field(..., description="Unique identifier for the violation")
    message: str = Field("", description="Hash of the violation identity (never raw text)")
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
        expires_at = self.expires_at
        if expires_at.tzinfo is not None and expires_at.utcoffset() is not None:
            expires_at = expires_at.astimezone(timezone.utc)
            return datetime.now(timezone.utc) > expires_at
        return datetime.now() > expires_at

    def matches(
        self,
        file_path: str,
        line_number: int,
        violation_type: str,
        message: str = "",
        violation_id: str = "",
    ) -> bool:
        """
        Check if this entry matches a violation.

        Path+line+type alone is not an identity (that is a suppression
        oracle). Require a matching message or violation_id.
        """
        if (
            self.file_path != file_path
            or self.line_number != line_number
            or self.violation_type != violation_type
            or self.is_expired
        ):
            return False
        query = (message or "").strip()
        stored = (self.message or "").strip()
        if query and stored and messages_match(stored, query):
            return True
        vid = (violation_id or "").strip()
        if vid and vid == self.violation_id:
            return True
        return False

    def matches_fuzzy(self, file_path: str, violation_type: str, message: str) -> bool:
        """
        Fuzzy match for violations where line numbers may shift.

        Empty or whitespace messages are not identities: matching on them
        would suppress every same-file/type finding.

        Args:
            file_path: File path to check
            violation_type: Type of violation
            message: Violation message to compare

        Returns:
            True if this entry likely matches the violation
        """
        query = (message or "").strip()
        stored = (self.message or "").strip()
        if not query or not stored or not messages_match(stored, query):
            return False
        return (
            self.file_path == file_path
            and self.violation_type == violation_type
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
        if not (entry.message or "").strip():
            # Empty message is a file+type wildcard under fuzzy match.
            entry.message = entry.violation_id
        entry.message = hash_violation_message(entry.message)
        self.entries.append(entry)
        self.updated_at = datetime.now()

    def remove_entry(
        self,
        violation_id: str,
        file_path: str = "",
        line_number: Optional[int] = None,
    ) -> bool:
        """Remove exactly one entry. Ambiguous IDs are not deleted."""
        candidates = [e for e in self.entries if e.violation_id == violation_id]
        if file_path:
            candidates = [e for e in candidates if e.file_path == file_path]
        if line_number is not None:
            candidates = [e for e in candidates if e.line_number == line_number]
        if len(candidates) != 1:
            return False
        target = candidates[0]
        self.entries = [e for e in self.entries if e is not target]
        self.updated_at = datetime.now()
        return True

    def find_match(
        self,
        file_path: str,
        line_number: int,
        violation_type: str,
        message: str = "",
        violation_id: str = "",
    ) -> Optional[BaselineEntry]:
        """Find a matching baseline entry (message or violation_id required)."""
        for entry in self.entries:
            if entry.matches(
                file_path, line_number, violation_type, message, violation_id
            ):
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
        if not (message or "").strip():
            return None
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
