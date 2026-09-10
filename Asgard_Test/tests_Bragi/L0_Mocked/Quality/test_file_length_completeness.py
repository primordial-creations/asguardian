"""Strict SDK-facing analysis must preserve findings and observed I/O failures."""

import builtins
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages import _confined_walk
from Asgard.Bragi.Quality.models.analysis_models import AnalysisConfig
from Asgard.Bragi.Quality.services import file_length_analyzer
from Asgard.Bragi.Quality.utilities.file_utils import count_lines


def analyzer():
    return file_length_analyzer.FileAnalyzer(AnalysisConfig(threshold=1))


def test_real_clean_and_finding_directory_with_spaces(tmp_path):
    target = tmp_path / "source files"
    target.mkdir()
    source = target / "source.py"
    source.write_text("one\n")
    clean = analyzer().analyze(target, strict_io=True)
    assert clean.analysis_complete and not clean.has_violations
    source.write_text("one\ntwo\n")
    finding = analyzer().analyze(target, strict_io=True)
    assert finding.analysis_complete and finding.has_violations
    assert finding.violations[0].relative_path == "source.py"
    assert not analyzer().analyze(target).analysis_complete


def test_failed_read_is_incomplete_with_surviving_finding(tmp_path, monkeypatch):
    good, bad = tmp_path / "good.py", tmp_path / "bad.py"
    good.write_text("one\ntwo\n")
    bad.write_text("secret\n")
    original = builtins.open

    def guarded_open(path, *args, **kwargs):
        if Path(path) == bad:
            raise PermissionError("controlled read denial")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    result = analyzer().analyze(tmp_path, strict_io=True)
    assert not result.analysis_complete
    assert len(result.analysis_errors) == 1
    assert result.analysis_errors[0].startswith("read: PermissionError:")
    assert result.has_violations
    assert result.violations[0].relative_path == "good.py"
    assert count_lines(bad) == 0  # Existing callers retain compatibility.
    with pytest.raises(PermissionError):
        count_lines(bad, strict_io=True)


def test_traversal_error_retains_previous_findings(tmp_path, monkeypatch):
    (tmp_path / "good.py").write_text("one\ntwo\n")

    def broken_walk(root, *, followlinks, onerror):
        yield str(root), [], ["good.py"]
        onerror(PermissionError("controlled directory denial"))

    monkeypatch.setattr(_confined_walk.os, "walk", broken_walk)
    result = analyzer().analyze(tmp_path, strict_io=True)
    assert result.has_violations and not result.analysis_complete
    assert result.analysis_errors[0].startswith("discovery: PermissionError:")


@pytest.mark.parametrize("directory", [False, True])
def test_escaping_symlink_is_incomplete_not_followed(tmp_path, directory):
    outside, target = tmp_path / "outside", tmp_path / "target"
    outside.mkdir()
    target.mkdir()
    (outside / "outside.py").write_text("one\ntwo\n")
    (target / "escape.py").symlink_to(outside if directory else outside / "outside.py")
    result = analyzer().analyze(target, strict_io=True)
    assert not result.analysis_complete and not result.has_violations
    assert result.analysis_errors


def test_excluded_directory_link_does_not_expand_scope(tmp_path):
    (tmp_path / "node_modules").symlink_to(tmp_path.parent)
    assert analyzer().analyze(tmp_path, strict_io=True).analysis_complete


def test_invalid_target_and_root_symlink_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        analyzer().analyze(tmp_path / "missing", strict_io=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(ValueError):
        analyzer().analyze(link, strict_io=True)
