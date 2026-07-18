"""
ASGARD_NO_CACHE read-only-target safety: with the env set, Bragi's
dependency-graph and license disk caches must write nothing into the
scanned path.
"""

from pathlib import Path

import pytest

from Asgard.Bragi.Dependencies.services.graph_service import (
    DependencyGraphService,
    no_cache_env,
)
from Asgard.Bragi.Dependencies.services._license_cache import LicenseDiskCache


@pytest.fixture()
def project(tmp_path):
    (tmp_path / "a.py").write_text("import b\n")
    (tmp_path / "b.py").write_text("X = 1\n")
    return tmp_path


def test_no_cache_env_parsing(monkeypatch):
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)
    assert no_cache_env() is False
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("ASGARD_NO_CACHE", value)
        assert no_cache_env() is True
    monkeypatch.setenv("ASGARD_NO_CACHE", "0")
    assert no_cache_env() is False


def test_graph_service_writes_nothing_with_env(project, monkeypatch):
    monkeypatch.setenv("ASGARD_NO_CACHE", "1")
    service = DependencyGraphService()
    assert service.use_disk_cache is False
    service.build(project)
    assert not (project / ".asgard_cache").exists()


def test_graph_service_still_caches_without_env(project, monkeypatch):
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)
    DependencyGraphService().build(project)
    assert (project / ".asgard_cache" / "bragi_dep_graph.json").exists()


def test_license_cache_disabled_with_env(project, monkeypatch):
    monkeypatch.setenv("ASGARD_NO_CACHE", "1")
    cache = LicenseDiskCache(Path(project))
    cache.put("requests", {"license_name": "Apache-2.0"})
    cache.save()
    assert not (project / ".asgard_cache").exists()


def test_license_cache_saves_without_env(project, monkeypatch):
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)
    cache = LicenseDiskCache(Path(project))
    cache.put("requests", {"license_name": "Apache-2.0"})
    cache.save()
    assert (project / ".asgard_cache" / "bragi_license_cache.json").exists()


def test_heimdall_scan_parser_accepts_no_cache():
    from Asgard.Heimdall.cli.main import create_parser

    args = create_parser().parse_args(["scan", ".", "--no-cache"])
    assert args.no_cache is True
