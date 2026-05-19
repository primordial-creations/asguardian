"""
Tests for Baseline Management Infrastructure

Comprehensive unit tests for BaselineConfig, BaselineEntry, BaselineStats,
BaselineFile, BaselineManager, and BaselineMixin.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from Asgard.common.baseline import (
    BaselineConfig,
    BaselineEntry,
    BaselineFile,
    BaselineManager,
    BaselineMixin,
    BaselineStats,
)


class TestBaselineConfig:
    """Tests for BaselineConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BaselineConfig()
        assert config.enabled is False
        assert config.baseline_file == ".asgard-baseline.json"
        assert config.default_expiry_days == 90
        assert config.fuzzy_matching is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BaselineConfig(
            enabled=True,
            baseline_file=".custom-baseline.json",
            default_expiry_days=180,
            fuzzy_matching=True,
        )
        assert config.enabled is True
        assert config.baseline_file == ".custom-baseline.json"
        assert config.default_expiry_days == 180
        assert config.fuzzy_matching is True


class TestBaselineEntry:
    """Tests for BaselineEntry dataclass."""

    def test_initialization_minimal(self):
        """Test minimal initialization."""
        entry = BaselineEntry(
            item_id="test_id",
            item_type="security",
            location="file.py:10",
        )
        assert entry.item_id == "test_id"
        assert entry.item_type == "security"
        assert entry.location == "file.py:10"
        assert entry.message == ""
        assert entry.reason == ""
        assert entry.created_by == "asguardian"
        assert entry.expires_at is None
        assert entry.metadata == {}

    def test_initialization_full(self):
        """Test full initialization."""
        now = datetime.now().isoformat()
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        metadata = {"key": "value"}

        entry = BaselineEntry(
            item_id="test_id",
            item_type="quality",
            location="file.py:20",
            message="Test issue",
            reason="Technical debt",
            created_at=now,
            created_by="user",
            expires_at=expiry,
            metadata=metadata,
        )

        assert entry.item_id == "test_id"
        assert entry.message == "Test issue"
        assert entry.reason == "Technical debt"
        assert entry.created_at == now
        assert entry.created_by == "user"
        assert entry.expires_at == expiry
        assert entry.metadata == metadata

    def test_is_expired_no_expiry(self):
        """Test is_expired with no expiry date."""
        entry = BaselineEntry(
            item_id="test",
            item_type="type",
            location="loc",
            expires_at=None,
        )
        assert entry.is_expired is False

    def test_is_expired_future_date(self):
        """Test is_expired with future expiry date."""
        future = (datetime.now() + timedelta(days=30)).isoformat()
        entry = BaselineEntry(
            item_id="test",
            item_type="type",
            location="loc",
            expires_at=future,
        )
        assert entry.is_expired is False

    def test_is_expired_past_date(self):
        """Test is_expired with past expiry date."""
        past = (datetime.now() - timedelta(days=30)).isoformat()
        entry = BaselineEntry(
            item_id="test",
            item_type="type",
            location="loc",
            expires_at=past,
        )
        assert entry.is_expired is True

    def test_is_expired_invalid_date(self):
        """Test is_expired with invalid date format."""
        entry = BaselineEntry(
            item_id="test",
            item_type="type",
            location="loc",
            expires_at="invalid-date",
        )
        assert entry.is_expired is False

    def test_matches_exact_match(self):
        """Test exact matching."""
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
            message="SQL injection risk",
        )

        assert entry.matches("file.py:10", "security", fuzzy=False) is True
        assert entry.matches("file.py:20", "security", fuzzy=False) is False
        assert entry.matches("file.py:10", "quality", fuzzy=False) is False

    def test_matches_fuzzy_same_file(self):
        """Test fuzzy matching with same file."""
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
            message="SQL injection",
        )

        # Same file, different line
        assert entry.matches("file.py:20", "security", "SQL injection", fuzzy=True) is True
        assert entry.matches("file.py:30", "security", fuzzy=True) is True

    def test_matches_fuzzy_different_file(self):
        """Test fuzzy matching with different file."""
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file1.py:10",
            message="Issue",
        )

        assert entry.matches("file2.py:10", "security", "Issue", fuzzy=True) is False

    def test_matches_fuzzy_message_similarity(self):
        """Test fuzzy matching with message similarity."""
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
            message="SQL injection detected",
        )

        # Substring match - entry.message in message or message in entry.message
        assert entry.matches("file.py:20", "security", "SQL injection detected in query", fuzzy=True) is True
        # "SQL injection" is in "SQL injection detected"
        assert entry.matches("file.py:20", "security", "SQL injection", fuzzy=True) is True

    def test_matches_different_type(self):
        """Test matching fails with different type."""
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
        )

        assert entry.matches("file.py:10", "quality", fuzzy=False) is False
        assert entry.matches("file.py:10", "quality", fuzzy=True) is False


class TestBaselineStats:
    """Tests for BaselineStats dataclass."""

    def test_initialization(self):
        """Test stats initialization."""
        stats = BaselineStats()
        assert stats.total_entries == 0
        assert stats.active_entries == 0
        assert stats.expired_entries == 0
        assert stats.entries_by_type == {}
        assert stats.entries_by_location == {}

    def test_custom_values(self):
        """Test stats with custom values."""
        stats = BaselineStats(
            total_entries=10,
            active_entries=8,
            expired_entries=2,
            entries_by_type={'security': 5, 'quality': 5},
            entries_by_location={'file1.py': 3, 'file2.py': 7},
        )
        assert stats.total_entries == 10
        assert stats.active_entries == 8
        assert stats.expired_entries == 2


class TestBaselineFile:
    """Tests for BaselineFile dataclass."""

    def test_initialization(self):
        """Test baseline file initialization."""
        baseline = BaselineFile()
        assert baseline.version == "1.0.0"
        assert baseline.project_path == ""
        assert isinstance(baseline.created_at, datetime)
        assert isinstance(baseline.updated_at, datetime)
        assert baseline.entries == []
        assert baseline.metadata == {}

    def test_add_entry(self):
        """Test adding entry to baseline."""
        baseline = BaselineFile()
        entry = BaselineEntry(item_id="test", item_type="type", location="loc")

        baseline.add_entry(entry)

        assert len(baseline.entries) == 1
        assert baseline.entries[0] == entry

    def test_add_entry_updates_timestamp(self):
        """Test add_entry updates updated_at timestamp."""
        baseline = BaselineFile()
        old_time = baseline.updated_at

        import time
        time.sleep(0.01)

        entry = BaselineEntry(item_id="test", item_type="type", location="loc")
        baseline.add_entry(entry)

        assert baseline.updated_at > old_time

    def test_remove_entry_exists(self):
        """Test removing existing entry."""
        baseline = BaselineFile()
        entry = BaselineEntry(item_id="test123", item_type="type", location="loc")
        baseline.entries.append(entry)

        result = baseline.remove_entry("test123")

        assert result is True
        assert len(baseline.entries) == 0

    def test_remove_entry_not_exists(self):
        """Test removing non-existent entry."""
        baseline = BaselineFile()
        result = baseline.remove_entry("nonexistent")
        assert result is False

    def test_remove_entry_updates_timestamp(self):
        """Test remove_entry updates timestamp."""
        baseline = BaselineFile()
        entry = BaselineEntry(item_id="test", item_type="type", location="loc")
        baseline.entries.append(entry)
        old_time = baseline.updated_at

        import time
        time.sleep(0.01)

        baseline.remove_entry("test")
        assert baseline.updated_at > old_time

    def test_find_match_exact(self):
        """Test finding exact match."""
        baseline = BaselineFile()
        entry = BaselineEntry(item_id="test", item_type="security", location="file.py:10")
        baseline.entries.append(entry)

        match = baseline.find_match("file.py:10", "security", fuzzy=False)
        assert match == entry

    def test_find_match_not_found(self):
        """Test find_match returns None when not found."""
        baseline = BaselineFile()
        match = baseline.find_match("file.py:10", "security", fuzzy=False)
        assert match is None

    def test_find_match_expired_ignored(self):
        """Test find_match ignores expired entries."""
        baseline = BaselineFile()
        past = (datetime.now() - timedelta(days=30)).isoformat()
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
            expires_at=past,
        )
        baseline.entries.append(entry)

        match = baseline.find_match("file.py:10", "security", fuzzy=False)
        assert match is None

    def test_find_match_fuzzy(self):
        """Test fuzzy matching."""
        baseline = BaselineFile()
        entry = BaselineEntry(
            item_id="test",
            item_type="security",
            location="file.py:10",
            message="SQL injection",
        )
        baseline.entries.append(entry)

        match = baseline.find_match("file.py:20", "security", "SQL injection", fuzzy=True)
        assert match == entry

    def test_get_stats(self):
        """Test getting baseline statistics."""
        baseline = BaselineFile()

        # Add active entries
        baseline.entries.append(BaselineEntry(item_id="1", item_type="security", location="file1.py:10"))
        baseline.entries.append(BaselineEntry(item_id="2", item_type="security", location="file2.py:20"))
        baseline.entries.append(BaselineEntry(item_id="3", item_type="quality", location="file1.py:30"))

        # Add expired entry
        past = (datetime.now() - timedelta(days=30)).isoformat()
        baseline.entries.append(BaselineEntry(
            item_id="4",
            item_type="quality",
            location="file3.py:40",
            expires_at=past,
        ))

        stats = baseline.get_stats()

        assert stats.total_entries == 4
        assert stats.active_entries == 3
        assert stats.expired_entries == 1
        assert stats.entries_by_type == {'security': 2, 'quality': 2}
        assert stats.entries_by_location == {'file1.py': 2, 'file2.py': 1, 'file3.py': 1}

    def test_clean_expired(self):
        """Test cleaning expired entries."""
        baseline = BaselineFile()

        # Add active entries
        baseline.entries.append(BaselineEntry(item_id="1", item_type="type", location="loc1"))
        baseline.entries.append(BaselineEntry(item_id="2", item_type="type", location="loc2"))

        # Add expired entries
        past = (datetime.now() - timedelta(days=30)).isoformat()
        baseline.entries.append(BaselineEntry(item_id="3", item_type="type", location="loc3", expires_at=past))
        baseline.entries.append(BaselineEntry(item_id="4", item_type="type", location="loc4", expires_at=past))

        removed = baseline.clean_expired()

        assert removed == 2
        assert len(baseline.entries) == 2
        assert all(e.item_id in ['1', '2'] for e in baseline.entries)

    def test_clean_expired_none_expired(self):
        """Test clean_expired with no expired entries."""
        baseline = BaselineFile()
        baseline.entries.append(BaselineEntry(item_id="1", item_type="type", location="loc"))

        removed = baseline.clean_expired()
        assert removed == 0


class TestBaselineManager:
    """Tests for BaselineManager class."""

    def test_initialization_default(self):
        """Test manager initialization with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            assert manager.project_path == Path(tmpdir)
            assert isinstance(manager.config, BaselineConfig)
            assert manager.baseline_path == Path(tmpdir) / ".asgard-baseline.json"
            assert manager._baseline is None

    def test_initialization_custom_config(self):
        """Test manager initialization with custom config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BaselineConfig(baseline_file=".custom.json")
            manager = BaselineManager(Path(tmpdir), config)

            assert manager.baseline_path == Path(tmpdir) / ".custom.json"

    def test_load_creates_new_baseline(self):
        """Test load creates new baseline if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))
            baseline = manager.load()

            assert isinstance(baseline, BaselineFile)
            assert baseline.entries == []

    def test_load_existing_baseline(self):
        """Test loading existing baseline file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_file = Path(tmpdir) / ".asgard-baseline.json"

            # Create baseline file
            data = {
                'version': '1.0.0',
                'project_path': str(tmpdir),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'entries': [
                    {
                        'item_id': 'test1',
                        'item_type': 'security',
                        'location': 'file.py:10',
                        'message': 'Issue',
                        'reason': 'Known',
                        'created_at': datetime.now().isoformat(),
                        'created_by': 'user',
                        'expires_at': None,
                        'metadata': {},
                    }
                ],
                'metadata': {},
            }
            baseline_file.write_text(json.dumps(data))

            manager = BaselineManager(Path(tmpdir))
            baseline = manager.load()

            assert len(baseline.entries) == 1
            assert baseline.entries[0].item_id == 'test1'

    def test_load_invalid_json(self):
        """Test load handles invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_file = Path(tmpdir) / ".asgard-baseline.json"
            baseline_file.write_text("invalid json")

            manager = BaselineManager(Path(tmpdir))
            baseline = manager.load()

            assert isinstance(baseline, BaselineFile)
            assert baseline.entries == []

    def test_load_cached(self):
        """Test load returns cached baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))
            baseline1 = manager.load()
            baseline2 = manager.load()

            assert baseline1 is baseline2

    def test_save(self):
        """Test saving baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))
            baseline = manager.load()

            entry = BaselineEntry(item_id="test", item_type="type", location="loc")
            baseline.add_entry(entry)

            manager.save()

            assert manager.baseline_path.exists()

            # Verify content
            with open(manager.baseline_path) as f:
                data = json.load(f)

            assert len(data['entries']) == 1
            assert data['entries'][0]['item_id'] == 'test'

    def test_create_from_items(self):
        """Test creating baseline from items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            items = [
                {'loc': 'file1.py:10', 'msg': 'Issue 1'},
                {'loc': 'file2.py:20', 'msg': 'Issue 2'},
                {'loc': 'file3.py:30', 'msg': 'Issue 3'},
            ]

            count = manager.create_from_items(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
                message_func=lambda x: x['msg'],
                reason='Initial baseline',
            )

            assert count == 3
            baseline = manager.load()
            assert len(baseline.entries) == 3

    def test_create_from_items_with_expiry(self):
        """Test creating baseline with expiry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            items = [{'loc': 'file.py:10'}]

            manager.create_from_items(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
                expiry_days=30,
            )

            baseline = manager.load()
            entry = baseline.entries[0]
            assert entry.expires_at is not None

    def test_create_from_items_skips_duplicates(self):
        """Test create_from_items skips existing entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            items = [{'loc': 'file.py:10'}]

            # Add first time
            count1 = manager.create_from_items(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            # Add again
            count2 = manager.create_from_items(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            assert count1 == 1
            assert count2 == 0

    def test_filter_items(self):
        """Test filtering items against baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            # Create baseline
            baselined_items = [{'loc': 'file1.py:10'}, {'loc': 'file2.py:20'}]
            manager.create_from_items(
                baselined_items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            # Filter items
            all_items = [
                {'loc': 'file1.py:10'},  # Baselined
                {'loc': 'file2.py:20'},  # Baselined
                {'loc': 'file3.py:30'},  # New
                {'loc': 'file4.py:40'},  # New
            ]

            new_items = manager.filter_items(
                all_items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            assert len(new_items) == 2
            assert new_items[0]['loc'] == 'file3.py:30'
            assert new_items[1]['loc'] == 'file4.py:40'

    def test_filter_items_with_message(self):
        """Test filtering with message matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BaselineConfig(fuzzy_matching=True)
            manager = BaselineManager(Path(tmpdir), config)

            # Create baseline
            manager.create_from_items(
                [{'loc': 'file.py:10', 'msg': 'SQL injection'}],
                item_type='security',
                location_func=lambda x: x['loc'],
                message_func=lambda x: x['msg'],
            )

            # Filter with different line but same message
            items = [
                {'loc': 'file.py:20', 'msg': 'SQL injection detected'},  # Should match
                {'loc': 'file.py:30', 'msg': 'XSS vulnerability'},  # Should not match
            ]

            new_items = manager.filter_items(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
                message_func=lambda x: x['msg'],
            )

            assert len(new_items) == 1
            assert new_items[0]['msg'] == 'XSS vulnerability'

    def test_add_entry(self):
        """Test manually adding entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            result = manager.add_entry(
                location='file.py:10',
                item_type='security',
                message='Issue',
                reason='Known issue',
            )

            assert result is True
            baseline = manager.load()
            assert len(baseline.entries) == 1

    def test_add_entry_duplicate(self):
        """Test adding duplicate entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            manager.add_entry('file.py:10', 'security')
            result = manager.add_entry('file.py:10', 'security')

            assert result is False

    def test_remove_entry(self):
        """Test removing entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            # Add entry
            manager.add_entry('file.py:10', 'security')
            baseline = manager.load()
            item_id = baseline.entries[0].item_id

            # Remove entry
            result = manager.remove_entry(item_id)

            assert result is True
            assert len(baseline.entries) == 0

    def test_clean_expired(self):
        """Test cleaning expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            # Add active entry
            manager.add_entry('file1.py:10', 'security', expiry_days=30)

            # Add expired entry manually with past expiration
            past = (datetime.now() - timedelta(days=10)).isoformat()
            baseline = manager.load()
            baseline.entries.append(BaselineEntry(
                item_id='expired',
                item_type='security',
                location='file2.py:20',
                expires_at=past,
            ))
            manager.save()

            count = manager.clean_expired()

            assert count == 1
            baseline = manager.load()
            assert len(baseline.entries) == 1

    def test_get_stats(self):
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            manager.add_entry('file1.py:10', 'security')
            manager.add_entry('file2.py:20', 'quality')

            stats = manager.get_stats()

            assert stats.total_entries == 2
            assert stats.active_entries == 2

    def test_list_entries_all(self):
        """Test listing all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            manager.add_entry('file1.py:10', 'security')
            manager.add_entry('file2.py:20', 'quality')

            entries = manager.list_entries()

            assert len(entries) == 2

    def test_list_entries_by_type(self):
        """Test listing entries by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            manager.add_entry('file1.py:10', 'security')
            manager.add_entry('file2.py:20', 'security')
            manager.add_entry('file3.py:30', 'quality')

            entries = manager.list_entries(item_type='security')

            assert len(entries) == 2

    def test_list_entries_by_location_pattern(self):
        """Test listing entries by location pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BaselineManager(Path(tmpdir))

            manager.add_entry('src/file1.py:10', 'security')
            manager.add_entry('src/file2.py:20', 'security')
            manager.add_entry('test/file3.py:30', 'security')

            entries = manager.list_entries(location_pattern='src/')

            assert len(entries) == 2


class TestBaselineMixin:
    """Tests for BaselineMixin class."""

    def test_init_baseline(self):
        """Test initializing baseline manager."""
        class TestClass(BaselineMixin):
            def __init__(self):
                self.baseline_config = BaselineConfig(enabled=True)
                self._baseline_manager = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_baseline(Path(tmpdir))

            assert obj._baseline_manager is not None
            assert isinstance(obj._baseline_manager, BaselineManager)

    def test_filter_baselined(self):
        """Test filtering baselined items."""
        class TestClass(BaselineMixin):
            def __init__(self):
                self.baseline_config = BaselineConfig(enabled=True)
                self._baseline_manager = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_baseline(Path(tmpdir))

            # Create baseline
            obj._baseline_manager.add_entry('file1.py:10', 'security')
            obj._baseline_manager.add_entry('file2.py:20', 'security')

            # Filter items
            items = [
                {'loc': 'file1.py:10'},  # Baselined
                {'loc': 'file2.py:20'},  # Baselined
                {'loc': 'file3.py:30'},  # New
            ]

            new_items = obj._filter_baselined(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            assert len(new_items) == 1
            assert new_items[0]['loc'] == 'file3.py:30'

    def test_filter_baselined_when_disabled(self):
        """Test filter returns all items when disabled."""
        class TestClass(BaselineMixin):
            def __init__(self):
                self.baseline_config = BaselineConfig(enabled=False)
                self._baseline_manager = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_baseline(Path(tmpdir))

            items = [{'loc': 'file.py:10'}]
            result = obj._filter_baselined(items, 'security', lambda x: x['loc'])

            assert result == items

    def test_create_baseline(self):
        """Test creating baseline from items."""
        class TestClass(BaselineMixin):
            def __init__(self):
                self.baseline_config = BaselineConfig(enabled=True)
                self._baseline_manager = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_baseline(Path(tmpdir))

            items = [{'loc': 'file.py:10'}, {'loc': 'file.py:20'}]
            count = obj._create_baseline(
                items,
                item_type='security',
                location_func=lambda x: x['loc'],
            )

            assert count == 2

    def test_get_baseline_stats(self):
        """Test getting baseline statistics."""
        class TestClass(BaselineMixin):
            def __init__(self):
                self.baseline_config = BaselineConfig(enabled=True)
                self._baseline_manager = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_baseline(Path(tmpdir))

            obj._baseline_manager.add_entry('file.py:10', 'security')

            stats = obj._get_baseline_stats()

            assert stats.total_entries == 1
