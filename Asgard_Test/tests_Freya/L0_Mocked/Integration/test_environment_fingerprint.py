"""L0 tests: environment fingerprinting and mismatch policy (Plan 04)."""

import asyncio
import json

import pytest

from Asgard.Freya.Integration.models.integration_models import (
    BaselineEntry,
    EnvironmentFingerprint,
)
from Asgard.Freya.Integration.services._baseline_manager_helpers import (
    ENV_MISMATCH_RATIONALE,
    capture_fingerprint,
    classify_fingerprint_mismatch,
    load_index,
    save_index,
)


def _fingerprint(**overrides) -> EnvironmentFingerprint:
    base = dict(
        os_name="Linux", os_release="6.17", browser_name="chromium",
        browser_version="120.0", playwright_version="1.40",
        viewport="1920x1080", device_scale_factor=1.0,
        font_stack_hash="abc123",
    )
    base.update(overrides)
    return EnvironmentFingerprint(**base)


class TestClassifyMismatch:
    def test_identical_is_none(self):
        assert classify_fingerprint_mismatch(_fingerprint(), _fingerprint()) == ("none", [])

    @pytest.mark.parametrize("field,value", [
        ("device_scale_factor", 2.0),
        ("viewport", "1280x720"),
        ("os_name", "Darwin"),
    ])
    def test_hard_fields(self, field, value):
        level, fields = classify_fingerprint_mismatch(
            _fingerprint(), _fingerprint(**{field: value}))
        assert level == "hard"
        assert field in fields

    @pytest.mark.parametrize("field,value", [
        ("browser_version", "121.0"),
        ("font_stack_hash", "zzz999"),
    ])
    def test_soft_fields(self, field, value):
        level, fields = classify_fingerprint_mismatch(
            _fingerprint(), _fingerprint(**{field: value}))
        assert level == "soft"
        assert fields == [field]

    def test_hard_includes_soft_fields_in_report(self):
        level, fields = classify_fingerprint_mismatch(
            _fingerprint(),
            _fingerprint(os_name="Darwin", font_stack_hash="zzz"))
        assert level == "hard"
        assert set(fields) == {"os_name", "font_stack_hash"}

    def test_missing_fingerprint_is_unverified(self):
        assert classify_fingerprint_mismatch(None, _fingerprint())[0] == "unverified"
        assert classify_fingerprint_mismatch(_fingerprint(), None)[0] == "unverified"

    def test_empty_field_values_not_compared(self):
        level, _ = classify_fingerprint_mismatch(
            _fingerprint(browser_version=""), _fingerprint(browser_version="121"))
        assert level == "none"


class TestCaptureFingerprint:
    def test_capture_without_page_uses_platform(self):
        fingerprint = asyncio.run(
            capture_fingerprint(viewport_width=800, viewport_height=600,
                                device_scale_factor=2.0)
        )
        assert fingerprint.os_name
        assert fingerprint.viewport == "800x600"
        assert fingerprint.device_scale_factor == 2.0
        assert fingerprint.browser_name == "chromium"


class TestLegacyBaselines:
    def _entry_dict(self, with_fingerprint: bool) -> dict:
        entry = {
            "url": "http://x", "name": "home",
            "created_at": "t", "updated_at": "t",
            "screenshot_path": "/tmp/a.png",
            "viewport_width": 1920, "viewport_height": 1080,
            "device": None, "hash": "deadbeef", "metadata": {},
        }
        if with_fingerprint:
            entry["fingerprint"] = _fingerprint().model_dump()
        return entry

    def test_legacy_index_without_fingerprint_loads(self, tmp_path):
        index_file = tmp_path / "baselines.json"
        index_file.write_text(json.dumps({"k1": self._entry_dict(False)}))
        baselines = load_index(index_file)
        assert baselines["k1"].fingerprint is None

    def test_index_roundtrip_with_fingerprint(self, tmp_path):
        index_file = tmp_path / "baselines.json"
        entry = BaselineEntry(**self._entry_dict(True))
        save_index(index_file, {"k1": entry})
        loaded = load_index(index_file)
        assert loaded["k1"].fingerprint.os_name == "Linux"

    def test_rationale_names_the_environment(self):
        assert "measures the environment" in ENV_MISMATCH_RATIONALE
