"""
Baseline Management Infrastructure

Manages creating, loading, and filtering violations against baselines.
Used to suppress known issues and track technical debt.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar('T')


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
    location: str  # file:line or URL or other location
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
            # For fuzzy matching, compare file path only (ignore line number)
            self_file = self.location.rsplit(':', 1)[0] if ':' in self.location else self.location
            other_file = location.rsplit(':', 1)[0] if ':' in location else location
            if self_file != other_file:
                return False
            # Also check message similarity if provided
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

            # By type
            stats.entries_by_type[entry.item_type] = stats.entries_by_type.get(entry.item_type, 0) + 1

            # By location (file only)
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


class BaselineManager:
    """
    Manages baseline files for suppressing known issues.

    Usage:
        manager = BaselineManager(project_path)

        # Create baseline from current issues
        manager.create_from_items(issues, "security", id_func, location_func)

        # Filter issues against baseline
        new_issues = manager.filter_items(issues, "security", id_func, location_func)

        # Get stats
        stats = manager.get_stats()
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[BaselineConfig] = None,
    ):
        """
        Initialize the baseline manager.

        Args:
            project_path: Root path of the project
            config: Baseline configuration
        """
        self.project_path = project_path or Path.cwd()
        self.config = config or BaselineConfig()
        self.baseline_path = self.project_path / self.config.baseline_file
        self._baseline: Optional[BaselineFile] = None

    def load(self) -> BaselineFile:
        """Load the baseline file."""
        if self._baseline is not None:
            return self._baseline

        if self.baseline_path.exists():
            try:
                with open(self.baseline_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                entries = [BaselineEntry(**e) for e in data.get('entries', [])]
                self._baseline = BaselineFile(
                    version=data.get('version', '1.0.0'),
                    project_path=data.get('project_path', str(self.project_path)),
                    created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
                    updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
                    entries=entries,
                    metadata=data.get('metadata', {}),
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                self._baseline = BaselineFile(project_path=str(self.project_path))
        else:
            self._baseline = BaselineFile(project_path=str(self.project_path))

        return self._baseline

    def save(self) -> None:
        """Save the baseline file to disk."""
        if self._baseline is None:
            return

        self._baseline.updated_at = datetime.now()

        data = {
            'version': self._baseline.version,
            'project_path': self._baseline.project_path,
            'created_at': self._baseline.created_at.isoformat(),
            'updated_at': self._baseline.updated_at.isoformat(),
            'entries': [
                {
                    'item_id': e.item_id,
                    'item_type': e.item_type,
                    'location': e.location,
                    'message': e.message,
                    'reason': e.reason,
                    'created_at': e.created_at,
                    'created_by': e.created_by,
                    'expires_at': e.expires_at,
                    'metadata': e.metadata,
                }
                for e in self._baseline.entries
            ],
            'metadata': self._baseline.metadata,
        }

        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def create_from_items(
        self,
        items: List[T],
        item_type: str,
        location_func: Callable[[T], str],
        message_func: Optional[Callable[[T], str]] = None,
        reason: str = "Initial baseline",
        created_by: str = "asguardian",
        expiry_days: Optional[int] = None,
    ) -> int:
        """
        Create baseline entries from a list of items.

        Args:
            items: List of items to baseline
            item_type: Type identifier for these items
            location_func: Function to get location from item
            message_func: Function to get message from item (optional)
            reason: Reason for baselining
            created_by: Who created this baseline
            expiry_days: Days until entries expire (None = use default)

        Returns:
            Number of entries created
        """
        baseline = self.load()
        count = 0

        expiry_days = expiry_days or self.config.default_expiry_days
        expires_at = (datetime.now() + timedelta(days=expiry_days)).isoformat() if expiry_days > 0 else None

        for item in items:
            location = location_func(item)
            message = message_func(item) if message_func else ""

            # Generate unique ID
            item_id = self._generate_id(location, item_type, message)

            # Check if already baselined
            if baseline.find_match(location, item_type, message, self.config.fuzzy_matching):
                continue

            entry = BaselineEntry(
                item_id=item_id,
                item_type=item_type,
                location=location,
                message=message,
                reason=reason,
                created_by=created_by,
                expires_at=expires_at,
            )

            baseline.add_entry(entry)
            count += 1

        self.save()
        return count

    def filter_items(
        self,
        items: List[T],
        item_type: str,
        location_func: Callable[[T], str],
        message_func: Optional[Callable[[T], str]] = None,
    ) -> List[T]:
        """
        Filter items against the baseline.

        Args:
            items: List of items to filter
            item_type: Type identifier
            location_func: Function to get location from item
            message_func: Function to get message from item (optional)

        Returns:
            List of items NOT in baseline (new items)
        """
        baseline = self.load()
        new_items = []

        for item in items:
            location = location_func(item)
            message = message_func(item) if message_func else ""

            match = baseline.find_match(
                location, item_type, message, self.config.fuzzy_matching
            )

            if match is None:
                new_items.append(item)

        return new_items

    def add_entry(
        self,
        location: str,
        item_type: str,
        message: str = "",
        reason: str = "",
        created_by: str = "asguardian",
        expiry_days: Optional[int] = None,
    ) -> bool:
        """
        Manually add a baseline entry.

        Returns:
            True if entry was added, False if already exists
        """
        baseline = self.load()

        if baseline.find_match(location, item_type, message, self.config.fuzzy_matching):
            return False

        expiry_days = expiry_days or self.config.default_expiry_days
        expires_at = (datetime.now() + timedelta(days=expiry_days)).isoformat() if expiry_days > 0 else None

        entry = BaselineEntry(
            item_id=self._generate_id(location, item_type, message),
            item_type=item_type,
            location=location,
            message=message,
            reason=reason,
            created_by=created_by,
            expires_at=expires_at,
        )

        baseline.add_entry(entry)
        self.save()
        return True

    def remove_entry(self, item_id: str) -> bool:
        """Remove a baseline entry by ID."""
        baseline = self.load()
        result = baseline.remove_entry(item_id)
        if result:
            self.save()
        return result

    def clean_expired(self) -> int:
        """Remove expired entries."""
        baseline = self.load()
        count = baseline.clean_expired()
        if count > 0:
            self.save()
        return count

    def get_stats(self) -> BaselineStats:
        """Get baseline statistics."""
        return self.load().get_stats()

    def list_entries(
        self,
        item_type: Optional[str] = None,
        location_pattern: Optional[str] = None,
    ) -> List[BaselineEntry]:
        """List baseline entries with optional filtering."""
        entries = self.load().entries

        if item_type:
            entries = [e for e in entries if e.item_type == item_type]

        if location_pattern:
            entries = [e for e in entries if location_pattern in e.location]

        return entries

    def _generate_id(self, location: str, item_type: str, message: str) -> str:
        """Generate a unique ID for an entry."""
        content = f"{location}:{item_type}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class BaselineMixin:
    """
    Mixin class to add baseline support to any scanner/analyzer.

    Usage:
        class MyScanner(BaselineMixin):
            def __init__(self, config):
                self.baseline_config = BaselineConfig(
                    enabled=config.baseline is not None,
                    baseline_file=config.baseline or ".asgard-baseline.json",
                )
                self._init_baseline(Path(config.path))

            def analyze(self, items):
                results = self._do_analysis(items)
                if self.baseline_config.enabled:
                    results = self._filter_baselined(results, "my_type")
                return results
    """

    baseline_config: BaselineConfig
    _baseline_manager: Optional[BaselineManager] = None

    def _init_baseline(self, project_path: Path) -> None:
        """Initialize baseline manager."""
        self._baseline_manager = BaselineManager(project_path, self.baseline_config)

    def _filter_baselined(
        self,
        items: List[T],
        item_type: str,
        location_func: Callable[[T], str],
        message_func: Optional[Callable[[T], str]] = None,
    ) -> List[T]:
        """Filter items against baseline."""
        if not self._baseline_manager or not self.baseline_config.enabled:
            return items
        return self._baseline_manager.filter_items(items, item_type, location_func, message_func)

    def _create_baseline(
        self,
        items: List[T],
        item_type: str,
        location_func: Callable[[T], str],
        message_func: Optional[Callable[[T], str]] = None,
        reason: str = "Baseline created",
    ) -> int:
        """Create baseline from items."""
        if not self._baseline_manager:
            return 0
        return self._baseline_manager.create_from_items(
            items, item_type, location_func, message_func, reason
        )

    def _get_baseline_stats(self) -> BaselineStats:
        """Get baseline statistics."""
        if not self._baseline_manager:
            return BaselineStats()
        return self._baseline_manager.get_stats()
