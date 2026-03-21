"""
Baseline Management Infrastructure

Manages creating, loading, and filtering violations against baselines.
Used to suppress known issues and track technical debt.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, TypeVar

from Asgard.common._baseline_models import (
    BaselineConfig,
    BaselineEntry,
    BaselineFile,
    BaselineStats,
)

T = TypeVar('T')


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

            item_id = self._generate_id(location, item_type, message)

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
