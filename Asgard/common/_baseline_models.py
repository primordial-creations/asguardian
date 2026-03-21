"""
Baseline Management Infrastructure - Data Models

Data model classes for the baseline management system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BaselineConfig:
    """Configuration for baseline management."""
    enabled: bool = False
    baseline_file: str = ".asgard-baseline.json"
    default_expiry_days: int = 90
    fuzzy_matching: bool = False


@dataclass
class BaselineEntry:
    """A single baseline entry."""
    item_id: str
    item_type: str
    location: str
    message: str = ""
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = "asguardian"
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expiry
        except ValueError:
            return False

    def matches(
        self,
        location: str,
        item_type: str,
        message: Optional[str] = None,
        fuzzy: bool = False,
    ) -> bool:
        """
        Check if this entry matches given criteria.

        Args:
            location: Location to match
            item_type: Item type to match
            message: Message to match (optional, for fuzzy matching)
            fuzzy: Use fuzzy matching (ignore line numbers)

        Returns:
            True if matches
        """
        if self.item_type != item_type:
            return False

        if fuzzy:
            self_file = self.location.rsplit(':', 1)[0] if ':' in self.location else self.location
            other_file = location.rsplit(':', 1)[0] if ':' in location else location
            if self_file != other_file:
                return False
            if message and self.message:
                return self.message in message or message in self.message
            return True
        else:
            return self.location == location


@dataclass
class BaselineStats:
    """Statistics about a baseline."""
    total_entries: int = 0
    active_entries: int = 0
    expired_entries: int = 0
    entries_by_type: Dict[str, int] = field(default_factory=dict)
    entries_by_location: Dict[str, int] = field(default_factory=dict)


@dataclass
class BaselineFile:
    """A baseline file containing multiple entries."""
    version: str = "1.0.0"
    project_path: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    entries: List[BaselineEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_entry(self, entry: BaselineEntry) -> None:
        """Add an entry to the baseline."""
        self.entries.append(entry)
        self.updated_at = datetime.now()

    def remove_entry(self, item_id: str) -> bool:
        """Remove an entry by ID."""
        for i, entry in enumerate(self.entries):
            if entry.item_id == item_id:
                del self.entries[i]
                self.updated_at = datetime.now()
                return True
        return False

    def find_match(
        self,
        location: str,
        item_type: str,
        message: Optional[str] = None,
        fuzzy: bool = False,
    ) -> Optional[BaselineEntry]:
        """Find a matching entry."""
        for entry in self.entries:
            if not entry.is_expired and entry.matches(location, item_type, message, fuzzy):
                return entry
        return None

    def get_stats(self) -> BaselineStats:
        """Get baseline statistics."""
        stats = BaselineStats()
        stats.total_entries = len(self.entries)

        for entry in self.entries:
            if entry.is_expired:
                stats.expired_entries += 1
            else:
                stats.active_entries += 1

            stats.entries_by_type[entry.item_type] = stats.entries_by_type.get(entry.item_type, 0) + 1

            loc = entry.location.rsplit(':', 1)[0] if ':' in entry.location else entry.location
            stats.entries_by_location[loc] = stats.entries_by_location.get(loc, 0) + 1

        return stats

    def clean_expired(self) -> int:
        """Remove expired entries."""
        before = len(self.entries)
        self.entries = [e for e in self.entries if not e.is_expired]
        removed = before - len(self.entries)
        if removed > 0:
            self.updated_at = datetime.now()
        return removed
