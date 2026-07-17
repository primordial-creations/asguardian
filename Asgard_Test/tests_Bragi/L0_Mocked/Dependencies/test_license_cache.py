"""
Tests for the license disk cache (Plan 03 Phase D): the previously dead
`use_cache` / `cache_expiry_days` config is now backed by
`.asgard_cache/bragi_license_cache.json`, installed-metadata resolution
replaces the `pip show` subprocess, and PyPI is only a parallel fallback.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Asgard.Bragi.Dependencies.models.license_models import LicenseConfig
from Asgard.Bragi.Dependencies.services._license_cache import (
    CACHE_RELATIVE_PATH,
    LicenseDiskCache,
)
from Asgard.Bragi.Dependencies.services.license_checker import LicenseChecker


class TestLicenseDiskCache:
    def test_put_get_roundtrip(self, tmp_path):
        cache = LicenseDiskCache(tmp_path, expiry_days=7)
        cache.put("Requests", {"version": "2.28.0", "license_name": "Apache-2.0"})
        record = cache.get("requests")  # case-insensitive
        assert record["license_name"] == "Apache-2.0"

    def test_persists_across_instances(self, tmp_path):
        first = LicenseDiskCache(tmp_path, expiry_days=7)
        first.put("pkg", {"license_name": "MIT"})
        first.save()
        assert (tmp_path / CACHE_RELATIVE_PATH).exists()
        second = LicenseDiskCache(tmp_path, expiry_days=7)
        assert second.get("pkg")["license_name"] == "MIT"

    def test_expiry_honours_cache_expiry_days(self, tmp_path):
        cache = LicenseDiskCache(tmp_path, expiry_days=7)
        cache.put("pkg", {"license_name": "MIT"})
        cache.save()
        fresh = LicenseDiskCache(
            tmp_path, expiry_days=7,
            now=datetime.now() + timedelta(days=6))
        assert fresh.get("pkg") is not None
        stale = LicenseDiskCache(
            tmp_path, expiry_days=7,
            now=datetime.now() + timedelta(days=8))
        assert stale.get("pkg") is None

    def test_corrupt_cache_treated_as_empty(self, tmp_path):
        path = tmp_path / CACHE_RELATIVE_PATH
        path.parent.mkdir(parents=True)
        path.write_text("{not json")
        cache = LicenseDiskCache(tmp_path, expiry_days=7)
        assert cache.get("anything") is None


class TestCheckerUsesLocalMetadataAndCache:
    def test_installed_package_resolved_without_network(self, tmp_path, monkeypatch):
        (tmp_path / "requirements.txt").write_text("pytest>=7\n")
        checker = LicenseChecker(LicenseConfig(scan_path=tmp_path))

        def boom(*a, **k):
            raise AssertionError("network fallback must not be hit")
        monkeypatch.setattr(checker, "_get_license_from_pypi", boom)

        result = checker.analyze()
        assert result.total_packages == 1
        assert result.packages[0].source == "installed"
        assert result.packages[0].version

    def test_analyze_writes_and_reuses_disk_cache(self, tmp_path, monkeypatch):
        (tmp_path / "requirements.txt").write_text("pytest>=7\n")
        LicenseChecker(LicenseConfig(scan_path=tmp_path)).analyze()
        assert (tmp_path / CACHE_RELATIVE_PATH).exists()

        checker = LicenseChecker(LicenseConfig(scan_path=tmp_path))

        def boom(*a, **k):
            raise AssertionError("cached package must not re-resolve")
        monkeypatch.setattr(checker, "_get_license_from_installed", boom)
        monkeypatch.setattr(checker, "_get_license_from_pypi", boom)
        result = checker.analyze()
        assert result.total_packages == 1

    def test_use_cache_false_writes_nothing(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest>=7\n")
        checker = LicenseChecker(LicenseConfig(scan_path=tmp_path,
                                               use_cache=False))
        checker.analyze()
        assert not (tmp_path / CACHE_RELATIVE_PATH).exists()

    def test_unknown_package_falls_back_to_pypi_parallel(self, tmp_path, monkeypatch):
        (tmp_path / "requirements.txt").write_text(
            "no-such-pkg-a==1.0\nno-such-pkg-b==1.0\n")
        checker = LicenseChecker(LicenseConfig(scan_path=tmp_path))
        calls = []

        def fake_pypi(name):
            calls.append(name)
            return None
        monkeypatch.setattr(checker, "_get_license_from_pypi", fake_pypi)
        result = checker.analyze()
        assert sorted(calls) == ["no-such-pkg-a", "no-such-pkg-b"]
        assert all(p.source == "not_found" for p in result.packages)
        # Deterministic ordering: sorted by name.
        assert [p.package_name for p in result.packages] == sorted(
            p.package_name for p in result.packages)
