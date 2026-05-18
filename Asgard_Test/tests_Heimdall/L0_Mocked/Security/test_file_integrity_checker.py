"""Tests for file integrity checker."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.FileIntegrity.services.file_integrity_checker import FileIntegrityChecker
from Asgard.Heimdall.Security.FileIntegrity.models.file_integrity_models import (
    FileIntegrityReport,
    FileRecord,
)


class TestFileIntegrityCheckerInstantiation:
    def test_checker_can_be_instantiated(self):
        assert FileIntegrityChecker() is not None


class TestFileIntegrityCheckerBaseline:
    def test_create_and_verify_detects_modification(self, tmp_path):
        baseline_file = str(tmp_path / ".baseline.json")
        checker = FileIntegrityChecker(baseline_file=baseline_file)
        (tmp_path / "data.txt").write_text("original content")
        checker.create_baseline(tmp_path)
        (tmp_path / "data.txt").write_text("tampered content")
        report: FileIntegrityReport = checker.verify_integrity(tmp_path)
        assert report.modified or report.has_changes

    def test_unchanged_files_produce_no_modifications(self, tmp_path):
        baseline_file = str(tmp_path / ".baseline.json")
        checker = FileIntegrityChecker(baseline_file=baseline_file)
        (tmp_path / "data.txt").write_text("stable content")
        checker.create_baseline(tmp_path)
        report: FileIntegrityReport = checker.verify_integrity(tmp_path)
        assert len(report.modified) == 0


class TestFileIntegrityCheckerHashing:
    def test_same_file_produces_consistent_hash(self, tmp_path):
        checker = FileIntegrityChecker()
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        record1 = checker.hash_file(f)
        record2 = checker.hash_file(f)
        assert record1 is not None
        assert record2 is not None
        assert record1.sha256 == record2.sha256
        assert record1.md5 == record2.md5
