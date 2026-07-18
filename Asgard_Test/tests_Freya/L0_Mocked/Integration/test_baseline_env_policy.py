"""L0 tests: BaselineManager environment-mismatch policy (Plan 04)."""

import asyncio
from datetime import datetime

import pytest

import Asgard.Freya.Integration.services.baseline_manager as bm_module
from Asgard.Freya.Integration.models.integration_models import (
    BaselineConfig,
    BaselineEntry,
    EnvironmentFingerprint,
)
from Asgard.Freya.Integration.services.baseline_manager import BaselineManager


class _FakeScreenshot:
    file_path = ""
    file_size_bytes = 0
    metadata: dict = {}


class _FakeCapture:
    def __init__(self, *args, **kwargs):
        pass

    async def capture_full_page(self, url):
        shot = _FakeScreenshot()
        shot.file_path = "/tmp/does-not-matter.png"
        return shot


class _FakeResult:
    is_similar = True
    similarity_score = 1.0
    diff_image_path = None


class _FakeTester:
    def __init__(self, *args, **kwargs):
        pass

    def compare(self, *args, **kwargs):
        return _FakeResult()


def _entry(tmp_path, fingerprint):
    return BaselineEntry(
        url="http://x", name="home",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        screenshot_path=str(tmp_path / "base.png"),
        viewport_width=1920, viewport_height=1080,
        device=None, hash="deadbeef", fingerprint=fingerprint,
    )


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(bm_module, "ScreenshotCapture", _FakeCapture)
    monkeypatch.setattr(bm_module, "VisualRegressionTester", _FakeTester)
    return BaselineManager(BaselineConfig(storage_directory=str(tmp_path)))


def _install_fingerprints(monkeypatch, current):
    async def fake_capture(*args, **kwargs):
        return current
    monkeypatch.setattr(bm_module, "capture_fingerprint", fake_capture)


def _mismatched_fp():
    return EnvironmentFingerprint(
        os_name="Darwin", viewport="1920x1080", device_scale_factor=2.0)


def _baseline_fp():
    return EnvironmentFingerprint(
        os_name="Linux", viewport="1920x1080", device_scale_factor=1.0)


def test_hard_mismatch_refused_by_default(manager, tmp_path, monkeypatch):
    entry = _entry(tmp_path, _baseline_fp())
    key = bm_module.generate_key("http://x", "home", None)
    manager.baselines[key] = entry
    _install_fingerprints(monkeypatch, _mismatched_fp())

    result = asyncio.run(manager.compare_to_baseline("http://x", "home"))
    assert result["status"] == "environment_mismatch"
    assert result["inconclusive"] is True
    assert set(result["mismatched_fields"]) >= {"os_name", "device_scale_factor"}
    assert "measures the environment" in result["rationale"]
    assert result["severity_cap"] == "major"


def test_hard_mismatch_override_runs_with_warning(manager, tmp_path, monkeypatch):
    key = bm_module.generate_key("http://x", "home", None)
    manager.baselines[key] = _entry(tmp_path, _baseline_fp())
    _install_fingerprints(monkeypatch, _mismatched_fp())

    result = asyncio.run(manager.compare_to_baseline(
        "http://x", "home", allow_env_mismatch=True))
    assert result["status"] == "compared"
    assert "HARD environment mismatch" in result["environment_warning"]
    assert result["severity_cap"] == "major"
    assert "Structural tripwire" in result["framing"]


def test_legacy_baseline_unverified_warning(manager, tmp_path, monkeypatch):
    key = bm_module.generate_key("http://x", "home", None)
    manager.baselines[key] = _entry(tmp_path, None)
    _install_fingerprints(monkeypatch, _baseline_fp())

    result = asyncio.run(manager.compare_to_baseline("http://x", "home"))
    assert result["status"] == "compared"
    assert "Unverified baseline environment" in result["environment_warning"]


def test_matching_environment_no_warning(manager, tmp_path, monkeypatch):
    key = bm_module.generate_key("http://x", "home", None)
    manager.baselines[key] = _entry(tmp_path, _baseline_fp())
    _install_fingerprints(monkeypatch, _baseline_fp())

    result = asyncio.run(manager.compare_to_baseline("http://x", "home"))
    assert result["environment_status"] == "none"
    assert result["environment_warning"] is None
    assert result["severity_cap"] is None
    assert "identical environment" in result["framing"]
