"""
Tests for Incremental Processing Infrastructure

Comprehensive unit tests for IncrementalConfig, HashEntry, FileHashCache,
and IncrementalMixin.
"""

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from Asgard.common.incremental import (
    FileHashCache,
    HashEntry,
    IncrementalConfig,
    IncrementalMixin,
)


class TestIncrementalConfig:
    """Tests for IncrementalConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = IncrementalConfig()
        assert config.enabled is False
        assert config.cache_path == ".asgard-cache.json"
        assert config.store_results is True
        assert config.max_cache_age_days == 30
        assert config.hash_func == "sha256"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = IncrementalConfig(
            enabled=True,
            cache_path=".custom-cache.json",
            store_results=False,
            max_cache_age_days=60,
            hash_func="md5",
        )
        assert config.enabled is True
        assert config.cache_path == ".custom-cache.json"
        assert config.store_results is False
        assert config.max_cache_age_days == 60
        assert config.hash_func == "md5"


class TestHashEntry:
    """Tests for HashEntry dataclass."""

    def test_initialization_minimal(self):
        """Test minimal initialization."""
        entry = HashEntry(item_id="test_id", hash="abc123")
        assert entry.item_id == "test_id"
        assert entry.hash == "abc123"
        assert entry.last_modified is None
        assert entry.size is None
        assert entry.result is None
        assert entry.metadata == {}

    def test_initialization_full(self):
        """Test full initialization."""
        now = datetime.now().isoformat()
        metadata = {"key": "value"}
        result = {"status": "success"}

        entry = HashEntry(
            item_id="test_id",
            hash="abc123",
            last_modified=123456.789,
            size=1024,
            last_processed=now,
            result=result,
            metadata=metadata,
        )

        assert entry.item_id == "test_id"
        assert entry.hash == "abc123"
        assert entry.last_modified == 123456.789
        assert entry.size == 1024
        assert entry.last_processed == now
        assert entry.result == result
        assert entry.metadata == metadata

    def test_default_last_processed(self):
        """Test last_processed defaults to current time."""
        entry = HashEntry(item_id="test", hash="hash")
        # Should be a valid ISO format datetime
        datetime.fromisoformat(entry.last_processed)


class TestFileHashCache:
    """Tests for FileHashCache class."""

    def test_initialization(self):
        """Test cache initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            config = IncrementalConfig(cache_path=".test-cache.json")
            cache = FileHashCache(project_path, config)

            assert cache.project_path == project_path
            assert cache.config == config
            assert cache.cache_file == project_path / ".test-cache.json"
            assert cache._entries == {}
            assert cache._dirty is False

    def test_initialization_default_config(self):
        """Test cache initialization with default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            assert isinstance(cache.config, IncrementalConfig)

    def test_load_nonexistent_file(self):
        """Test loading cache when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            result = cache.load()
            assert result is False
            assert cache._entries == {}

    def test_load_valid_cache(self):
        """Test loading valid cache file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            cache_file = project_path / ".asgard-cache.json"

            # Create a valid cache file
            data = {
                'version': '1.0.0',
                'created_at': datetime.now().isoformat(),
                'project_path': str(project_path),
                'entries': {
                    'item1': {
                        'item_id': 'item1',
                        'hash': 'hash1',
                        'last_modified': 123.456,
                        'size': 100,
                        'last_processed': datetime.now().isoformat(),
                        'result': {'status': 'ok'},
                        'metadata': {'key': 'value'},
                    }
                }
            }
            cache_file.write_text(json.dumps(data))

            cache = FileHashCache(project_path)
            result = cache.load()

            assert result is True
            assert 'item1' in cache._entries
            assert cache._entries['item1'].hash == 'hash1'
            assert cache._dirty is False

    def test_load_invalid_json(self):
        """Test loading cache with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            cache_file = project_path / ".asgard-cache.json"
            cache_file.write_text("invalid json {")

            cache = FileHashCache(project_path)
            result = cache.load()

            assert result is False
            assert cache._entries == {}

    def test_save_when_not_dirty(self):
        """Test save doesn't write when cache not dirty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            cache_file = project_path / ".asgard-cache.json"
            cache_file.write_text('{"version": "1.0.0"}')

            cache = FileHashCache(project_path)
            cache._dirty = False
            cache.save()

            # File should still exist but not be modified
            assert cache_file.exists()

    def test_save_creates_directory(self):
        """Test save creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "subdir" / "nested"
            cache = FileHashCache(project_path)
            cache._dirty = True
            cache.save()

            assert cache.cache_file.exists()
            assert cache.cache_file.parent.exists()

    def test_save_writes_entries(self):
        """Test save writes entries correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            cache = FileHashCache(project_path)

            entry = HashEntry(
                item_id='test_item',
                hash='test_hash',
                last_modified=123.456,
                size=100,
                result={'status': 'ok'},
                metadata={'key': 'value'},
            )
            cache._entries['test_item'] = entry
            cache._dirty = True
            cache.save()

            # Load and verify
            with open(cache.cache_file) as f:
                data = json.load(f)

            assert 'entries' in data
            assert 'test_item' in data['entries']
            assert data['entries']['test_item']['hash'] == 'test_hash'
            assert cache._dirty is False

    def test_compute_hash_string(self):
        """Test computing hash from string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir), IncrementalConfig(hash_func="sha256"))
            content = "test content"
            hash_result = cache.compute_hash(content)

            expected = hashlib.sha256(content.encode('utf-8')).hexdigest()
            assert hash_result == expected

    def test_compute_hash_bytes(self):
        """Test computing hash from bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir), IncrementalConfig(hash_func="sha256"))
            content = b"test content"
            hash_result = cache.compute_hash(content)

            expected = hashlib.sha256(content).hexdigest()
            assert hash_result == expected

    def test_compute_hash_file(self):
        """Test computing hash from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            content = "test file content"
            test_file.write_text(content)

            cache = FileHashCache(Path(tmpdir), IncrementalConfig(hash_func="sha256"))
            hash_result = cache.compute_hash(test_file)

            expected = hashlib.sha256(content.encode('utf-8')).hexdigest()
            assert hash_result == expected

    def test_compute_hash_sha1(self):
        """Test computing hash with SHA1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir), IncrementalConfig(hash_func="sha1"))
            content = "test"
            hash_result = cache.compute_hash(content)

            expected = hashlib.sha1(content.encode('utf-8')).hexdigest()
            assert hash_result == expected

    def test_compute_hash_md5(self):
        """Test computing hash with MD5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir), IncrementalConfig(hash_func="md5"))
            content = "test"
            hash_result = cache.compute_hash(content)

            expected = hashlib.md5(content.encode('utf-8')).hexdigest()
            assert hash_result == expected

    def test_is_changed_not_in_cache(self):
        """Test is_changed returns True for new items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            assert cache.is_changed('new_item') is True

    def test_is_changed_content_unchanged(self):
        """Test is_changed returns False for unchanged content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            content = "test content"
            hash_val = cache.compute_hash(content)

            cache._entries['item1'] = HashEntry(item_id='item1', hash=hash_val)

            assert cache.is_changed('item1', content) is False

    def test_is_changed_content_changed(self):
        """Test is_changed returns True for changed content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            old_hash = cache.compute_hash("old content")
            cache._entries['item1'] = HashEntry(item_id='item1', hash=old_hash)

            assert cache.is_changed('item1', "new content") is True

    def test_is_changed_file_quick_check_unchanged(self):
        """Test is_changed uses quick file stat check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")
            stat = test_file.stat()

            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(
                item_id='item1',
                hash='somehash',
                last_modified=stat.st_mtime,
                size=stat.st_size,
            )

            # Should use quick check and return False
            assert cache.is_changed('item1', file_path=test_file) is False

    def test_is_changed_file_stat_changed(self):
        """Test is_changed detects file stat changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(
                item_id='item1',
                hash='somehash',
                last_modified=999.0,  # Different mtime
                size=100,  # Different size
            )

            # Quick check fails, should do full hash check
            assert cache.is_changed('item1', file_path=test_file) is True

    def test_get_cached_result_exists(self):
        """Test getting cached result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            result = {'status': 'cached'}
            cache._entries['item1'] = HashEntry(
                item_id='item1',
                hash='hash',
                result=result,
            )

            cached = cache.get_cached_result('item1')
            assert cached == result

    def test_get_cached_result_not_exists(self):
        """Test getting cached result for non-existent item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            assert cache.get_cached_result('nonexistent') is None

    def test_get_cached_result_no_result(self):
        """Test getting cached result when entry has no result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(item_id='item1', hash='hash', result=None)

            assert cache.get_cached_result('item1') is None

    def test_update_with_content(self):
        """Test updating cache with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            content = "test content"
            result = {'status': 'processed'}

            cache.update('item1', content=content, result=result)

            assert 'item1' in cache._entries
            assert cache._entries['item1'].hash == cache.compute_hash(content)
            assert cache._entries['item1'].result == result
            assert cache._dirty is True

    def test_update_with_file(self):
        """Test updating cache with file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("file content")
            stat = test_file.stat()

            cache = FileHashCache(Path(tmpdir))
            cache.update('item1', file_path=test_file)

            entry = cache._entries['item1']
            assert entry.hash == cache.compute_hash(test_file)
            assert entry.last_modified == stat.st_mtime
            assert entry.size == stat.st_size

    def test_update_with_metadata(self):
        """Test updating cache with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            metadata = {'custom': 'data'}

            cache.update('item1', content="test", metadata=metadata)

            assert cache._entries['item1'].metadata == metadata

    def test_update_store_results_disabled(self):
        """Test update doesn't store results when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = IncrementalConfig(store_results=False)
            cache = FileHashCache(Path(tmpdir), config)

            cache.update('item1', content="test", result={'data': 'value'})

            assert cache._entries['item1'].result is None

    def test_invalidate_existing(self):
        """Test invalidating existing entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(item_id='item1', hash='hash')
            cache._dirty = False

            result = cache.invalidate('item1')

            assert result is True
            assert 'item1' not in cache._entries
            assert cache._dirty is True

    def test_invalidate_nonexistent(self):
        """Test invalidating non-existent entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            result = cache.invalidate('nonexistent')

            assert result is False

    def test_clear(self):
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(item_id='item1', hash='hash1')
            cache._entries['item2'] = HashEntry(item_id='item2', hash='hash2')
            cache._dirty = False

            cache.clear()

            assert cache._entries == {}
            assert cache._dirty is True

    def test_filter_changed(self):
        """Test filtering changed items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))

            # Add cached items
            cache._entries['1'] = HashEntry(item_id='1', hash=cache.compute_hash("content1"))
            cache._entries['2'] = HashEntry(item_id='2', hash=cache.compute_hash("old_content"))

            items = [
                {'id': '1', 'content': 'content1'},  # Unchanged
                {'id': '2', 'content': 'new_content'},  # Changed
                {'id': '3', 'content': 'content3'},  # New
            ]

            changed = cache.filter_changed(
                items,
                id_func=lambda x: x['id'],
                content_func=lambda x: x['content'],
            )

            assert len(changed) == 2
            assert changed[0]['id'] == '2'
            assert changed[1]['id'] == '3'

    def test_get_stats(self):
        """Test getting cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileHashCache(Path(tmpdir))
            cache._entries['item1'] = HashEntry(item_id='item1', hash='hash1', result={'data': 1})
            cache._entries['item2'] = HashEntry(item_id='item2', hash='hash2', result=None)
            cache._entries['item3'] = HashEntry(item_id='item3', hash='hash3', result={'data': 2})

            stats = cache.get_stats()

            assert stats['total_entries'] == 3
            assert stats['entries_with_results'] == 2
            assert stats['cache_file'] == str(cache.cache_file)
            assert stats['cache_exists'] is False


class TestIncrementalMixin:
    """Tests for IncrementalMixin class."""

    def test_init_cache(self):
        """Test initializing cache."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            assert obj._cache is not None
            assert isinstance(obj._cache, FileHashCache)

    def test_init_cache_loads_when_enabled(self):
        """Test cache is loaded when enabled."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a cache file
            cache_file = Path(tmpdir) / ".asgard-cache.json"
            cache_file.write_text(json.dumps({
                'version': '1.0.0',
                'entries': {
                    'item1': {
                        'item_id': 'item1',
                        'hash': 'hash1',
                        'last_modified': None,
                        'size': None,
                        'last_processed': datetime.now().isoformat(),
                        'result': None,
                        'metadata': {},
                    }
                }
            }))

            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            assert 'item1' in obj._cache._entries

    def test_is_changed(self):
        """Test _is_changed method."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            # New item should be changed
            assert obj._is_changed('item1', 'content') is True

            # Update cache
            obj._cache.update('item1', content='content')

            # Same content should not be changed
            assert obj._is_changed('item1', 'content') is False

            # Different content should be changed
            assert obj._is_changed('item1', 'new_content') is True

    def test_is_changed_when_disabled(self):
        """Test _is_changed always returns True when disabled."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=False)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            assert obj._is_changed('item1', 'content') is True

    def test_get_cached(self):
        """Test _get_cached method."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            result = {'status': 'cached'}
            obj._cache.update('item1', content='test', result=result)

            cached = obj._get_cached('item1')
            assert cached == result

    def test_get_cached_when_disabled(self):
        """Test _get_cached returns None when disabled."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=False)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            assert obj._get_cached('item1') is None

    def test_update_cache(self):
        """Test _update_cache method."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            obj._update_cache('item1', content='test', result={'data': 'value'})

            assert 'item1' in obj._cache._entries
            assert obj._cache._entries['item1'].result == {'data': 'value'}

    def test_save_cache(self):
        """Test _save_cache method."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            obj._cache.update('item1', content='test')
            obj._save_cache()

            assert obj._cache.cache_file.exists()

    def test_get_cache_stats(self):
        """Test _get_cache_stats method."""
        class TestClass(IncrementalMixin):
            def __init__(self):
                self.incremental_config = IncrementalConfig(enabled=True)
                self._cache = None

        with tempfile.TemporaryDirectory() as tmpdir:
            obj = TestClass()
            obj._init_cache(Path(tmpdir))

            obj._cache.update('item1', content='test')
            stats = obj._get_cache_stats()

            assert stats['total_entries'] == 1
