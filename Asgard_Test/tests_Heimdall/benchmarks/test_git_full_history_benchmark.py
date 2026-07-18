"""Benchmark corpus for the Git full-history / dangling-commit scan mode
(plan 07.3, RESEARCH_12). Default mode only reaches `git log --all`
history; a secret committed then force-pushed away still exists as a
dangling object until GC -- full_history=True finds it via `git fsck
--unreachable`.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.Git.services.git_scanner import GitSecurityScanner


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture
def repo_with_dangling_secret(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")

    (repo / "README.md").write_text("initial\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial commit")

    (repo / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n")
    _git(repo, "add", "id_rsa")
    _git(repo, "commit", "-q", "-m", "oops committed a key")

    # Force-push-equivalent locally: reset the branch back to the first
    # commit (dropping the id_rsa commit from all refs), then create a
    # new clean commit so the id_rsa commit becomes unreachable from any
    # branch/tag while still existing as a git object.
    _git(repo, "reset", "--hard", "HEAD~1")
    (repo / "README.md").write_text("clean\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "clean history")
    return repo


def test_default_mode_does_not_reach_dangling_commit(repo_with_dangling_secret):
    scanner = GitSecurityScanner(full_history=False)
    report = scanner.scan(repo_with_dangling_secret)
    assert not any(f.issue_type.startswith("dangling_") for f in report.findings)


def test_full_history_mode_finds_dangling_secret(repo_with_dangling_secret):
    scanner = GitSecurityScanner(full_history=True)
    report = scanner.scan(repo_with_dangling_secret)
    dangling = [f for f in report.findings if f.issue_type.startswith("dangling_")]
    assert dangling, "full_history=True must surface the id_rsa key from the dangling commit"
    assert "rotate" in dangling[0].recommendation.lower()
