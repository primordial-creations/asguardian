"""Tests for Asgard.Baseline.*"""
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from Asgard.Baseline.baseline_manager import BaselineManager
from Asgard.Baseline.models import BaselineEntry, BaselineFile, BaselineStats
from Asgard.Baseline._baseline_helpers import (
    generate_violation_id,
    get_violation_message,
    relative_path,
)


# ---------------------------------------------------------------------------
# BaselineEntry
# ---------------------------------------------------------------------------

class TestBaselineEntryInstantiation:
    def test_entry_can_be_instantiated(self):
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=10,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        assert entry is not None


class TestBaselineEntryCleanPath:
    def test_entry_matches_exact(self):
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=10,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        assert entry.matches("src/foo.py", 10, "lazy_import") is True

    def test_entry_not_expired_by_default(self):
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=10,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        assert entry.is_expired is False


class TestBaselineEntryEdgeCases:
    def test_entry_matches_wrong_line_returns_false(self):
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=10,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        assert entry.matches("src/foo.py", 99, "lazy_import") is False

    def test_entry_expired_when_expires_at_in_past(self):
        past = datetime.now() - timedelta(days=1)
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="abc123",
            expires_at=past,
        )
        assert entry.is_expired is True

    def test_entry_matches_returns_false_when_expired(self):
        past = datetime.now() - timedelta(days=1)
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="abc123",
            expires_at=past,
        )
        assert entry.matches("src/foo.py", 1, "lazy_import") is False

    def test_fuzzy_match(self):
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="abc123",
            message="some import",
        )
        assert entry.matches_fuzzy("src/foo.py", "lazy_import", "some import") is True


# ---------------------------------------------------------------------------
# BaselineFile
# ---------------------------------------------------------------------------

class TestBaselineFileInstantiation:
    def test_baseline_file_can_be_instantiated(self):
        assert BaselineFile() is not None


class TestBaselineFileCleanPath:
    def test_add_entry_increases_count(self):
        bf = BaselineFile()
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        bf.add_entry(entry)
        assert len(bf.entries) == 1

    def test_remove_entry_by_id(self):
        bf = BaselineFile()
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="abc123",
        )
        bf.add_entry(entry)
        result = bf.remove_entry("abc123")
        assert result is True
        assert len(bf.entries) == 0

    def test_get_stats_returns_baseline_stats(self):
        bf = BaselineFile()
        stats = bf.get_stats()
        assert isinstance(stats, BaselineStats)
        assert stats.total_entries == 0

    def test_find_match_returns_entry(self):
        bf = BaselineFile()
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=5,
            violation_type="complexity",
            violation_id="xyz",
        )
        bf.add_entry(entry)
        found = bf.find_match("src/foo.py", 5, "complexity")
        assert found is not None

    def test_clean_expired_removes_expired_entries(self):
        past = datetime.now() - timedelta(days=1)
        bf = BaselineFile()
        entry = BaselineEntry(
            file_path="src/foo.py",
            line_number=1,
            violation_type="lazy_import",
            violation_id="exp1",
            expires_at=past,
        )
        bf.add_entry(entry)
        removed = bf.clean_expired()
        assert removed == 1
        assert len(bf.entries) == 0


class TestBaselineFileEdgeCases:
    def test_remove_nonexistent_entry_returns_false(self):
        bf = BaselineFile()
        assert bf.remove_entry("no-such-id") is False

    def test_find_match_returns_none_when_not_present(self):
        bf = BaselineFile()
        assert bf.find_match("missing.py", 1, "lazy_import") is None

    def test_stats_entries_by_type(self):
        bf = BaselineFile()
        bf.add_entry(BaselineEntry(file_path="a.py", line_number=1,
                                   violation_type="lazy_import", violation_id="id1"))
        bf.add_entry(BaselineEntry(file_path="b.py", line_number=2,
                                   violation_type="lazy_import", violation_id="id2"))
        bf.add_entry(BaselineEntry(file_path="c.py", line_number=3,
                                   violation_type="complexity", violation_id="id3"))
        stats = bf.get_stats()
        assert stats.entries_by_type["lazy_import"] == 2
        assert stats.entries_by_type["complexity"] == 1


# ---------------------------------------------------------------------------
# BaselineManager
# ---------------------------------------------------------------------------

class TestBaselineManagerInstantiation:
    def test_manager_can_be_instantiated(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        assert manager is not None


class TestBaselineManagerCleanPath:
    def test_load_returns_baseline_file_when_no_file_exists(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        bf = manager.load()
        assert isinstance(bf, BaselineFile)

    def test_add_entry_and_save_persists_to_disk(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        result = manager.add_entry(
            file_path=str(tmp_path / "src" / "foo.py"),
            line_number=5,
            violation_type="lazy_import",
            message="import os",
            reason="known",
        )
        assert result is True
        assert manager.baseline_path.exists()

    def test_load_from_existing_file(self, tmp_path):
        bf = BaselineFile(project_path=str(tmp_path))
        baseline_path = tmp_path / ".asgard-baseline.json"
        baseline_path.write_text(
            json.dumps(bf.model_dump(mode="json"), default=str)
        )
        manager = BaselineManager(project_path=tmp_path)
        loaded = manager.load()
        assert isinstance(loaded, BaselineFile)

    def test_get_stats_empty_baseline(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        stats = manager.get_stats()
        assert stats.total_entries == 0

    def test_list_entries_empty(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        entries = manager.list_entries()
        assert entries == []

    def test_generate_report_text(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        report = manager.generate_report("text")
        assert isinstance(report, str)

    def test_generate_report_json(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        report = manager.generate_report("json")
        parsed = json.loads(report)
        assert isinstance(parsed, dict)

    def test_generate_report_markdown(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        report = manager.generate_report("markdown")
        assert isinstance(report, str)


class TestBaselineManagerEdgeCases:
    def test_add_duplicate_entry_returns_false(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        file_path = str(tmp_path / "foo.py")
        manager.add_entry(file_path=file_path, line_number=1, violation_type="lazy_import")
        second = manager.add_entry(file_path=file_path, line_number=1, violation_type="lazy_import")
        assert second is False

    def test_remove_nonexistent_entry_returns_false(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        assert manager.remove_entry("no-such-id") is False

    def test_clean_expired_returns_zero_when_no_expired(self, tmp_path):
        manager = BaselineManager(project_path=tmp_path)
        manager.add_entry(file_path=str(tmp_path / "a.py"), line_number=1,
                          violation_type="lazy_import")
        count = manager.clean_expired()
        assert count == 0

    def test_filter_violations_no_baseline_returns_all(self, tmp_path):
        class FakeViolation:
            def __init__(self):
                self.file_path = str(tmp_path / "a.py")
                self.line_number = 1
                self.message = "issue"
        manager = BaselineManager(project_path=tmp_path)
        violations = [FakeViolation(), FakeViolation()]
        filtered = manager.filter_violations(violations, "lazy_import")
        assert len(filtered) == len(violations)


# ---------------------------------------------------------------------------
# _baseline_helpers
# ---------------------------------------------------------------------------

class TestBaselineHelpersInstantiation:
    def test_generate_violation_id_returns_string(self):
        vid = generate_violation_id("src/foo.py", 10, "lazy_import", "import os")
        assert isinstance(vid, str)
        assert len(vid) == 12


class TestBaselineHelpersCleanPath:
    def test_generate_violation_id_deterministic(self):
        id1 = generate_violation_id("src/foo.py", 10, "lazy_import", "import os")
        id2 = generate_violation_id("src/foo.py", 10, "lazy_import", "import os")
        assert id1 == id2

    def test_relative_path_converts_absolute(self, tmp_path):
        abs_path = str(tmp_path / "src" / "foo.py")
        rel = relative_path(tmp_path, abs_path)
        assert rel == "src/foo.py"

    def test_get_violation_message_uses_message_attr(self):
        class V:
            message = "hello"
        assert get_violation_message(V()) == "hello"


class TestBaselineHelpersEdgeCases:
    def test_generate_violation_id_different_inputs_differ(self):
        id1 = generate_violation_id("src/foo.py", 1, "lazy_import", "")
        id2 = generate_violation_id("src/bar.py", 1, "lazy_import", "")
        assert id1 != id2

    def test_relative_path_returns_original_when_not_relative(self, tmp_path):
        other = "/some/other/path/foo.py"
        result = relative_path(tmp_path, other)
        assert result == other

    def test_get_violation_message_returns_empty_for_no_attr(self):
        class V:
            pass
        assert get_violation_message(V()) == ""
