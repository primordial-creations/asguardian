"""
Tests for Plan 03 Phase E: opt-in OSV vulnerability lookup (mocked; the
default path never touches the network) and the offline package-health table.
"""

import json

import pytest

from Asgard.Bragi.Dependencies.models.sbom_models import SBOMComponent
from Asgard.Bragi.Dependencies.services._package_health import (
    check_package_health,
)
from Asgard.Bragi.Dependencies.services.vulnerability_checker import (
    VulnerabilityChecker,
)


def component(name, version="1.0.0"):
    return SBOMComponent(
        name=name, version=version,
        version_resolution="resolved",
        purl=f"pkg:pypi/{name}@{version}",
    )


class TestOptInDiscipline:
    def test_default_path_never_checks_and_says_so(self, monkeypatch):
        checker = VulnerabilityChecker()  # no opt-in

        def boom(*a, **k):
            raise AssertionError("network must not be touched by default")
        monkeypatch.setattr(checker, "_post_batch", boom)
        result = checker.check_components([component("requests")])
        assert result.checked is False
        assert result.mode == "disabled"
        assert "opt-in" in result.reason
        assert not result.has_vulnerabilities  # but NOT a claimed clean scan

    def test_network_mode_requires_explicit_flag(self, monkeypatch):
        checker = VulnerabilityChecker(enable_network=True)
        monkeypatch.setattr(checker, "_post_batch", lambda batch: {
            "results": [
                {"vulns": [{"id": "GHSA-xxxx", "summary": "bad thing"}]},
            ]
        })
        result = checker.check_components([component("requests", "2.19.0")])
        assert result.checked is True and result.mode == "network"
        assert result.findings[0].vulnerability_id == "GHSA-xxxx"
        assert result.findings[0].confidence == "measured"

    def test_network_failure_is_graceful_and_honest(self, monkeypatch):
        import urllib.error
        checker = VulnerabilityChecker(enable_network=True)

        def down(batch):
            raise urllib.error.URLError("offline")
        monkeypatch.setattr(checker, "_post_batch", down)
        result = checker.check_components([component("requests")])
        assert result.checked is False
        assert "unreachable" in result.reason
        assert result.findings == []


class TestOfflineSnapshot:
    def test_snapshot_matches_by_name_and_version(self, tmp_path):
        snapshot = tmp_path / "advisories.json"
        snapshot.write_text(json.dumps({"advisories": [
            {"package": "requests", "id": "PYSEC-1", "summary": "cve",
             "affected_versions": ["2.19.0"]},
            {"package": "requests", "id": "PYSEC-2", "summary": "all versions",
             "affected_versions": None},
            {"package": "flask", "id": "PYSEC-3", "summary": "other pkg"},
        ]}))
        checker = VulnerabilityChecker(offline_snapshot_path=snapshot)
        result = checker.check_components([component("requests", "2.19.0")])
        assert result.checked and result.mode == "offline-snapshot"
        assert sorted(f.vulnerability_id for f in result.findings) == \
            ["PYSEC-1", "PYSEC-2"]

    def test_unaffected_version_not_flagged(self, tmp_path):
        snapshot = tmp_path / "advisories.json"
        snapshot.write_text(json.dumps({"advisories": [
            {"package": "requests", "id": "PYSEC-1",
             "affected_versions": ["2.19.0"]},
        ]}))
        checker = VulnerabilityChecker(offline_snapshot_path=snapshot)
        result = checker.check_components([component("requests", "2.31.0")])
        assert result.checked and result.findings == []

    def test_unreadable_snapshot_reported_not_clean(self, tmp_path):
        snapshot = tmp_path / "advisories.json"
        snapshot.write_text("{broken")
        checker = VulnerabilityChecker(offline_snapshot_path=snapshot)
        result = checker.check_components([component("requests")])
        assert result.checked is False
        assert "unreadable" in result.reason


class TestPackageHealth:
    def test_pycrypto_flagged_abandoned(self):
        result = check_package_health(["PyCrypto", "requests"])
        assert result.has_issues
        issue = result.issues[0]
        assert issue.package_name == "pycrypto"
        assert issue.status == "abandoned"
        assert issue.replacement == "pycryptodome"
        assert issue.severity == "high"

    def test_matching_is_canonical_never_substring(self):
        # "pycryptodome" contains "pycrypto" as a substring: must NOT match.
        result = check_package_health(["pycryptodome", "Pillow"])
        assert not result.has_issues

    def test_rename_detected_via_canonical_form(self):
        result = check_package_health(["Flask_Script"])
        assert result.issues[0].status == "abandoned"

    def test_clean_list(self):
        result = check_package_health(["requests", "pydantic"])
        assert result.packages_checked == 2
        assert result.issues == []
