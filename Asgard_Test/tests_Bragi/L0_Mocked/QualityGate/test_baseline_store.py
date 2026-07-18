"""
Tests for the per-branch fingerprint baseline store (Plan Heimdall-09 §1,
Bragi-06 §3.3 cache discipline, and the one-way baseline ratchet).
"""

import json

import pytest

from Asgard.Bragi.QualityGate.baseline_store import (
    BranchBaseline,
    FingerprintBaselineStore,
)


@pytest.fixture
def store(tmp_path):
    return FingerprintBaselineStore(tmp_path)


class TestCaptureAndLoad:
    def test_load_missing_returns_none(self, store):
        assert store.load("main") is None

    def test_capture_then_load_roundtrip(self, store):
        store.capture("main", "abc123", ["fp1", "fp2"])
        baseline = store.load("main")
        assert isinstance(baseline, BranchBaseline)
        assert baseline.commit == "abc123"
        assert baseline.fingerprint_set == {"fp1", "fp2"}

    def test_capture_deduplicates(self, store):
        store.capture("main", "abc", ["fp1", "fp1", "fp2"])
        assert sorted(store.load("main").fingerprints) == ["fp1", "fp2"]

    def test_multiple_branches_independent(self, store):
        store.capture("main", "a", ["fp1"])
        store.capture("release", "b", ["fp2"])
        assert store.load("main").fingerprint_set == {"fp1"}
        assert store.load("release").fingerprint_set == {"fp2"}
        assert store.branches() == ["main", "release"]

    def test_store_lives_under_asgard_cache(self, store, tmp_path):
        store.capture("main", "a", ["fp1"])
        assert (tmp_path / ".asgard_cache").exists()

    def test_corrupt_store_returns_none(self, store, tmp_path):
        store.capture("main", "a", ["fp1"])
        store.store_path.write_text("{not json", encoding="utf-8")
        assert store.load("main") is None

    def test_delete_branch(self, store):
        store.capture("main", "a", ["fp1"])
        assert store.delete("main") is True
        assert store.load("main") is None
        assert store.delete("main") is False


class TestRatchet:
    def test_ratchet_requires_existing_baseline(self, store):
        with pytest.raises(ValueError):
            store.ratchet_update("main", "sha", ["fp1"])

    def test_ratchet_retires_fixed_findings(self, store):
        store.capture("main", "a", ["fp1", "fp2", "fp3"])
        removed = store.ratchet_update("main", "b", ["fp1", "fp3"])
        assert removed == 1
        assert store.load("main").fingerprint_set == {"fp1", "fp3"}

    def test_ratchet_never_adds_new_findings(self, store):
        """One-way: new debt can never sneak into the baseline."""
        store.capture("main", "a", ["fp1"])
        store.ratchet_update("main", "b", ["fp1", "fpNEW"])
        assert store.load("main").fingerprint_set == {"fp1"}

    def test_ratchet_updates_commit(self, store):
        store.capture("main", "a", ["fp1"])
        store.ratchet_update("main", "newsha", ["fp1"])
        assert store.load("main").commit == "newsha"


class TestReadOnlyDiscipline:
    def test_load_does_not_write(self, store, tmp_path):
        """PR evaluations load read-only: loading must never create or touch the file."""
        assert store.load("main") is None
        assert not store.store_path.exists()

        store.capture("main", "a", ["fp1"])
        before = store.store_path.read_bytes()
        store.load("main")
        assert store.store_path.read_bytes() == before

    def test_store_is_plain_json(self, store):
        store.capture("main", "a", ["fp1"])
        data = json.loads(store.store_path.read_text(encoding="utf-8"))
        assert "branches" in data
