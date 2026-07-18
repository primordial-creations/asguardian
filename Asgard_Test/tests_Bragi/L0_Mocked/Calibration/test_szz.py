"""
Tests for the Plan 05 Stage-2 SZZ bug-inducing-commit trace.

Builds tiny, real (`git init`) throwaway repos in a tmp dir - the module is
pure git subprocess, so this is the only honest way to test it without
mocking subprocess (which would just re-assert the mock).
"""

import subprocess
from pathlib import Path

import pytest

from Asgard.Bragi.Calibration.models.calibration_models import SZZStatus
from Asgard.Bragi.Calibration.services.szz import (
    MIN_FIX_COMMITS,
    compute_szz,
    identify_bugfix_commits,
    is_bugfix_subject,
)


def _git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo)] + list(args), check=True, capture_output=True, text=True)


def _commit(repo: Path, message: str, files: dict):
    for name, content in files.items():
        (repo / name).write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message, "--no-gpg-sign")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    return r


class TestBugfixSubjectHeuristic:
    def test_matches_fix_keywords(self):
        assert is_bugfix_subject("fix: null pointer in parser")
        assert is_bugfix_subject("Fixed crash on empty input")
        assert is_bugfix_subject("hotfix login bug")
        assert is_bugfix_subject("patch CVE-2024-1234")

    def test_does_not_match_feature_commits(self):
        assert not is_bugfix_subject("add new export endpoint")
        assert not is_bugfix_subject("refactor: extract helper")


class TestIdentifyBugfixCommits:
    def test_finds_only_fix_commits(self, repo):
        _commit(repo, "initial commit", {"a.py": "x = 1\n"})
        _commit(repo, "add feature", {"a.py": "x = 1\ny = 2\n"})
        _commit(repo, "fix: off by one", {"a.py": "x = 1\ny = 3\n"})
        commits = identify_bugfix_commits(repo)
        assert len(commits) == 1
        assert "fix" in commits[0].subject.lower()

    def test_empty_outside_git_repo(self, tmp_path):
        not_a_repo = tmp_path / "plain"
        not_a_repo.mkdir()
        assert identify_bugfix_commits(not_a_repo) == []


class TestComputeSzz:
    def test_insufficient_data_below_min_fix_commits(self, repo):
        _commit(repo, "initial commit", {"a.py": "x = 1\n"})
        _commit(repo, "fix: typo", {"a.py": "x = 2\n"})
        result = compute_szz(repo, min_fix_commits=MIN_FIX_COMMITS)
        assert result.status == SZZStatus.INSUFFICIENT_DATA
        assert result.fix_commit_count == 1

    def test_traces_inducing_commit_for_modified_line(self, repo):
        # a.py's buggy line is introduced in commit 2, then fixed in commit 3.
        _commit(repo, "initial commit", {"a.py": "def f():\n    return 1\n"})
        _commit(repo, "add bug: wrong constant", {"a.py": "def f():\n    return 42\n"})
        # Pad with enough unrelated fix commits to clear the burn-in gate.
        for i in range(MIN_FIX_COMMITS - 1):
            _commit(repo, f"fix: unrelated issue {i}", {f"noise_{i}.py": f"n = {i}\n"})
        _commit(repo, "fix: wrong constant should be 1", {"a.py": "def f():\n    return 1\n"})

        result = compute_szz(repo, min_fix_commits=MIN_FIX_COMMITS)
        assert result.status == SZZStatus.OK
        assert result.fix_commit_count >= MIN_FIX_COMMITS
        assert result.induced_commit_counts.get("a.py", 0) >= 1

    def test_pure_addition_fix_has_nothing_to_blame(self, repo):
        # A fix that only *adds* a missing null-check line has no old-side
        # line to trace back to - the module must not crash or fabricate.
        _commit(repo, "initial commit", {"a.py": "def f(x):\n    return x.value\n"})
        for i in range(MIN_FIX_COMMITS):
            _commit(repo, f"fix: guard missing case {i}", {f"noise_{i}.py": f"n = {i}\n"})
        result = compute_szz(repo, min_fix_commits=MIN_FIX_COMMITS)
        assert result.status == SZZStatus.OK  # doesn't crash; just no trace for a.py
