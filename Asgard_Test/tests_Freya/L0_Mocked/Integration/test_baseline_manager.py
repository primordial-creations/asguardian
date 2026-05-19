"""
Freya Baseline Manager Tests

Comprehensive L0 unit tests for BaselineManager service.

After refactoring, several helper functions (load_index, save_index, generate_key,
calculate_hash, version_baseline) are module-level functions in
_baseline_manager_helpers. The BaselineManager class still exposes wrappers
(_generate_key, _calculate_hash, _version_baseline) for backwards compatibility.

These tests use tmp_path for real storage directories to keep things simple, and
patch only what is needed (ScreenshotCapture, VisualRegressionTester, shutil).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from Asgard.Freya.Integration.models.integration_models import BaselineConfig, BaselineEntry
from Asgard.Freya.Integration.services.baseline_manager import BaselineManager


@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / "baselines"


@pytest.fixture
def base_config(storage_dir):
    return BaselineConfig(
        storage_directory=str(storage_dir),
        auto_update=False,
        version_baselines=True,
        max_versions=5,
        diff_threshold=0.1,
    )


@pytest.fixture
def mock_baseline_entry():
    return BaselineEntry(
        url="https://example.com",
        name="test_baseline",
        created_at="2025-01-01T00:00:00",
        updated_at="2025-01-01T00:00:00",
        screenshot_path="/tmp/test_baselines/abc123/baseline_20250101_000000.png",
        viewport_width=1920,
        viewport_height=1080,
        hash="test_hash_12345",
    )


@pytest.fixture
def mock_screenshot_result():
    screenshot = Mock()
    screenshot.file_path = "/tmp/screenshots/capture.png"
    screenshot.metadata = {"format": "png"}
    screenshot.file_size_bytes = 12345
    return screenshot


@pytest.fixture
def mock_regression_result():
    result = Mock()
    result.is_similar = True
    result.similarity_score = 1.0
    result.diff_image_path = None
    return result


class TestBaselineManagerInit:
    def test_init_creates_storage_directory(self, storage_dir, base_config):
        manager = BaselineManager(config=base_config)
        assert storage_dir.exists()
        assert isinstance(manager.baselines, dict)

    def test_init_with_custom_config(self, base_config):
        manager = BaselineManager(config=base_config)
        assert manager.config == base_config

    def test_init_loads_existing_index(self, storage_dir):
        storage_dir.mkdir(parents=True)
        index_file = storage_dir / "baselines.json"
        index_data = {
            "abc123": {
                "url": "https://example.com",
                "name": "test",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "screenshot_path": "/path/to/screenshot.png",
                "viewport_width": 1920,
                "viewport_height": 1080,
                "hash": "test_hash",
            }
        }
        with open(index_file, "w") as f:
            json.dump(index_data, f)
        config = BaselineConfig(storage_directory=str(storage_dir))
        manager = BaselineManager(config=config)
        assert len(manager.baselines) == 1
        assert "abc123" in manager.baselines

    def test_init_creates_empty_index_if_no_file(self, base_config):
        manager = BaselineManager(config=base_config)
        assert manager.baselines == {}


class TestBaselineManagerLoadIndex:
    def test_load_index_existing_file(self, storage_dir):
        storage_dir.mkdir(parents=True)
        index_file = storage_dir / "baselines.json"
        index_data = {
            "abc123": {
                "url": "https://example.com",
                "name": "test",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "screenshot_path": "/path/to/screenshot.png",
                "viewport_width": 1920,
                "viewport_height": 1080,
                "hash": "test_hash",
            }
        }
        with open(index_file, "w") as f:
            json.dump(index_data, f)
        config = BaselineConfig(storage_directory=str(storage_dir))
        manager = BaselineManager(config=config)
        assert len(manager.baselines) == 1
        assert isinstance(manager.baselines["abc123"], BaselineEntry)

    def test_load_index_no_file(self, base_config):
        manager = BaselineManager(config=base_config)
        assert manager.baselines == {}


class TestBaselineManagerSaveIndex:
    def test_save_index(self, base_config, mock_baseline_entry):
        manager = BaselineManager(config=base_config)
        manager.baselines = {"abc123": mock_baseline_entry}
        manager._save_index()
        index_file = Path(base_config.storage_directory) / "baselines.json"
        assert index_file.exists()
        with open(index_file) as f:
            data = json.load(f)
        assert "abc123" in data


class TestBaselineManagerCreateBaseline:
    @patch("Asgard.Freya.Integration.services.baseline_manager.shutil.copy")
    @patch("Asgard.Freya.Integration.services.baseline_manager.calculate_hash", return_value="hash123")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_create_baseline_without_device(
        self, mock_screenshot_class, mock_hash, mock_copy, base_config, mock_screenshot_result
    ):
        mock_inst = AsyncMock()
        mock_inst.capture_full_page = AsyncMock(return_value=mock_screenshot_result)
        mock_screenshot_class.return_value = mock_inst

        manager = BaselineManager(config=base_config)
        import asyncio
        result = asyncio.run(manager.create_baseline(url="https://example.com", name="test_baseline"))
        assert isinstance(result, BaselineEntry)
        assert result.url == "https://example.com"
        assert result.name == "test_baseline"
        assert result.viewport_width == 1920
        mock_inst.capture_full_page.assert_called_once()

    @patch("Asgard.Freya.Integration.services.baseline_manager.shutil.copy")
    @patch("Asgard.Freya.Integration.services.baseline_manager.calculate_hash", return_value="hash123")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_create_baseline_with_device(
        self, mock_screenshot_class, mock_hash, mock_copy, base_config, mock_screenshot_result
    ):
        mock_inst = AsyncMock()
        mock_inst.capture_with_devices = AsyncMock(return_value=[mock_screenshot_result])
        mock_screenshot_class.return_value = mock_inst

        manager = BaselineManager(config=base_config)
        import asyncio
        result = asyncio.run(manager.create_baseline(url="https://example.com", name="test_baseline", device="iphone-14"))
        assert result.device == "iphone-14"
        mock_inst.capture_with_devices.assert_called_once_with("https://example.com", devices=["iphone-14"])

    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_create_baseline_device_not_found(self, mock_screenshot_class, base_config):
        mock_inst = AsyncMock()
        mock_inst.capture_with_devices = AsyncMock(return_value=[])
        mock_screenshot_class.return_value = mock_inst

        manager = BaselineManager(config=base_config)
        import asyncio
        with pytest.raises(ValueError, match="Device 'invalid-device' not found"):
            asyncio.run(manager.create_baseline(url="https://example.com", name="test_baseline", device="invalid-device"))

    @patch("Asgard.Freya.Integration.services.baseline_manager.version_baseline")
    @patch("Asgard.Freya.Integration.services.baseline_manager.shutil.copy")
    @patch("Asgard.Freya.Integration.services.baseline_manager.calculate_hash", return_value="hash123")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_create_baseline_with_versioning(
        self, mock_screenshot_class, mock_hash, mock_copy, mock_version, base_config, mock_screenshot_result
    ):
        mock_inst = AsyncMock()
        mock_inst.capture_full_page = AsyncMock(return_value=mock_screenshot_result)
        mock_screenshot_class.return_value = mock_inst
        base_config.version_baselines = True
        manager = BaselineManager(config=base_config)
        import asyncio
        asyncio.run(manager.create_baseline(url="https://example.com", name="test_baseline"))
        mock_version.assert_called_once()


class TestBaselineManagerUpdateBaseline:
    def test_update_baseline_existing(self, base_config, mock_baseline_entry):
        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}
        manager.create_baseline = AsyncMock(return_value=mock_baseline_entry)
        import asyncio
        asyncio.run(manager.update_baseline(url="https://example.com", name="test_baseline"))
        manager.create_baseline.assert_called_once()
        args = manager.create_baseline.call_args
        assert args[0][2] == 1920 or args[1].get("viewport_width", 1920) == 1920

    def test_update_baseline_new(self, base_config):
        manager = BaselineManager(config=base_config)
        manager.baselines = {}
        manager.create_baseline = AsyncMock(return_value=Mock())
        import asyncio
        asyncio.run(manager.update_baseline(url="https://example.com", name="new_baseline"))
        manager.create_baseline.assert_called_once()


class TestBaselineManagerCompareToBaseline:
    def test_compare_to_baseline_not_found(self, base_config):
        manager = BaselineManager(config=base_config)
        manager.baselines = {}
        import asyncio
        result = asyncio.run(manager.compare_to_baseline(url="https://example.com", name="nonexistent"))
        assert result["success"] is False
        assert "Baseline not found" in result["error"]

    @patch("Asgard.Freya.Integration.services.baseline_manager.VisualRegressionTester")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_compare_to_baseline_no_difference(
        self, mock_screenshot_class, mock_regression_class,
        base_config, mock_baseline_entry, mock_screenshot_result, mock_regression_result
    ):
        mock_screenshot_instance = AsyncMock()
        mock_screenshot_instance.capture_full_page = AsyncMock(return_value=mock_screenshot_result)
        mock_screenshot_class.return_value = mock_screenshot_instance
        mock_regression_instance = Mock()
        mock_regression_instance.compare = Mock(return_value=mock_regression_result)
        mock_regression_class.return_value = mock_regression_instance

        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}

        import asyncio
        result = asyncio.run(manager.compare_to_baseline(url="https://example.com", name="test_baseline"))
        assert result["success"] is True
        assert result["has_difference"] is False
        assert result["passed"] is True

    @patch("Asgard.Freya.Integration.services.baseline_manager.VisualRegressionTester")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_compare_to_baseline_with_difference(
        self, mock_screenshot_class, mock_regression_class,
        base_config, mock_baseline_entry, mock_screenshot_result
    ):
        regression_result = Mock()
        regression_result.is_similar = False
        regression_result.similarity_score = 0.948
        regression_result.diff_image_path = "/tmp/diff.png"

        mock_screenshot_instance = AsyncMock()
        mock_screenshot_instance.capture_full_page = AsyncMock(return_value=mock_screenshot_result)
        mock_screenshot_class.return_value = mock_screenshot_instance
        mock_regression_instance = Mock()
        mock_regression_instance.compare = Mock(return_value=regression_result)
        mock_regression_class.return_value = mock_regression_instance

        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}

        import asyncio
        result = asyncio.run(manager.compare_to_baseline(url="https://example.com", name="test_baseline"))
        assert result["success"] is True
        assert result["has_difference"] is True
        assert result["passed"] is False

    @patch("Asgard.Freya.Integration.services.baseline_manager.VisualRegressionTester")
    @patch("Asgard.Freya.Integration.services.baseline_manager.ScreenshotCapture")
    def test_compare_to_baseline_auto_update(
        self, mock_screenshot_class, mock_regression_class,
        storage_dir, mock_baseline_entry, mock_screenshot_result
    ):
        regression_result = Mock()
        regression_result.is_similar = False
        regression_result.similarity_score = 0.948
        regression_result.diff_image_path = "/tmp/diff.png"

        mock_screenshot_instance = AsyncMock()
        mock_screenshot_instance.capture_full_page = AsyncMock(return_value=mock_screenshot_result)
        mock_screenshot_class.return_value = mock_screenshot_instance
        mock_regression_instance = Mock()
        mock_regression_instance.compare = Mock(return_value=regression_result)
        mock_regression_class.return_value = mock_regression_instance

        config = BaselineConfig(storage_directory=str(storage_dir), auto_update=True)
        manager = BaselineManager(config=config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}
        manager.update_baseline = AsyncMock()

        import asyncio
        asyncio.run(manager.compare_to_baseline(url="https://example.com", name="test_baseline"))
        manager.update_baseline.assert_called_once()


class TestBaselineManagerListBaselines:
    def test_list_baselines_all(self, base_config, mock_baseline_entry):
        entry2 = BaselineEntry(
            url="https://different.com", name="other",
            created_at="2025-01-01T00:00:00", updated_at="2025-01-01T00:00:00",
            screenshot_path="/path/to/other.png",
            viewport_width=1920, viewport_height=1080, hash="other_hash",
        )
        manager = BaselineManager(config=base_config)
        manager.baselines = {"abc": mock_baseline_entry, "def": entry2}
        assert len(manager.list_baselines()) == 2

    def test_list_baselines_filtered_by_url(self, base_config, mock_baseline_entry):
        entry2 = BaselineEntry(
            url="https://different.com", name="other",
            created_at="2025-01-01T00:00:00", updated_at="2025-01-01T00:00:00",
            screenshot_path="/path/to/other.png",
            viewport_width=1920, viewport_height=1080, hash="other_hash",
        )
        manager = BaselineManager(config=base_config)
        manager.baselines = {"abc": mock_baseline_entry, "def": entry2}
        results = manager.list_baselines(url="https://example.com")
        assert len(results) == 1
        assert results[0].url == "https://example.com"


class TestBaselineManagerGetBaseline:
    def test_get_baseline_exists(self, base_config, mock_baseline_entry):
        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}
        result = manager.get_baseline("https://example.com", "test_baseline")
        assert result == mock_baseline_entry

    def test_get_baseline_not_exists(self, base_config):
        manager = BaselineManager(config=base_config)
        manager.baselines = {}
        result = manager.get_baseline("https://example.com", "nonexistent")
        assert result is None


class TestBaselineManagerDeleteBaseline:
    def test_delete_baseline_exists(self, base_config, mock_baseline_entry):
        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        manager.baselines = {key: mock_baseline_entry}
        # mock_baseline_entry has a path that won't exist; that's fine
        result = manager.delete_baseline("https://example.com", "test_baseline")
        assert result is True
        assert key not in manager.baselines

    def test_delete_baseline_not_exists(self, base_config):
        manager = BaselineManager(config=base_config)
        manager.baselines = {}
        result = manager.delete_baseline("https://example.com", "nonexistent")
        assert result is False


class TestBaselineManagerGetVersions:
    def test_get_versions_exist(self, base_config):
        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        versions_dir = Path(base_config.storage_directory) / key / "versions"
        versions_dir.mkdir(parents=True)
        (versions_dir / "v_20250101_000000.png").write_bytes(b"a")
        (versions_dir / "v_20250102_000000.png").write_bytes(b"b")
        results = manager.get_versions("https://example.com", "test_baseline")
        assert len(results) == 2

    def test_get_versions_not_exist(self, base_config):
        manager = BaselineManager(config=base_config)
        results = manager.get_versions("https://example.com", "nonexistent")
        assert results == []


class TestBaselineManagerPrivateMethods:
    def test_generate_key_without_device(self, base_config):
        manager = BaselineManager(config=base_config)
        key = manager._generate_key("https://example.com", "test_baseline", None)
        assert isinstance(key, str)
        assert len(key) == 16

    def test_generate_key_with_device(self, base_config):
        manager = BaselineManager(config=base_config)
        key1 = manager._generate_key("https://example.com", "test_baseline", None)
        key2 = manager._generate_key("https://example.com", "test_baseline", "iphone-14")
        assert key1 != key2

    def test_calculate_hash(self, base_config, tmp_path):
        manager = BaselineManager(config=base_config)
        img = tmp_path / "img.png"
        img.write_bytes(b"test_image_data")
        h = manager._calculate_hash(str(img))
        assert isinstance(h, str)
        assert len(h) == 32

    def test_version_baseline(self, base_config, tmp_path):
        manager = BaselineManager(config=base_config)
        src = tmp_path / "src.png"
        src.write_bytes(b"data")
        manager._version_baseline("abc123", str(src))
        versions = list((Path(base_config.storage_directory) / "abc123" / "versions").glob("*.png"))
        assert len(versions) == 1

    def test_version_baseline_max_versions(self, storage_dir):
        config = BaselineConfig(storage_directory=str(storage_dir), max_versions=5)
        manager = BaselineManager(config=config)
        versions_dir = storage_dir / "abc123" / "versions"
        versions_dir.mkdir(parents=True)
        # Pre-create 7 existing versions (will create 8th below)
        import time
        for i in range(7):
            p = versions_dir / f"v_2025010{i}_000000.png"
            p.write_bytes(b"v")
        src = storage_dir / "src.png"
        src.write_bytes(b"new")
        manager._version_baseline("abc123", str(src))
        remaining = sorted(versions_dir.glob("*.png"))
        assert len(remaining) == 5
