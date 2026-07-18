"""Tests for the git friction collector (Plan 02 Phase D)."""

import subprocess
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.models.debt_models import FileFriction
from Asgard.Bragi.Quality.services._git_friction import (
    collect_friction,
    compute_interest_scores,
    is_minefield,
    is_sleeping_bear,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "Tester", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Tester", "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "initial commit")
    (repo / "a.py").write_text("x = 2\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "fix: correct value")
    return repo


class TestCollectFriction:
    def test_graceful_degradation_outside_git_repo(self, tmp_path: Path) -> None:
        result = collect_friction(tmp_path)
        assert result == {}

    def test_graceful_degradation_missing_path(self) -> None:
        result = collect_friction(Path("/nonexistent/path/xyz"))
        assert result == {}

    def test_collects_churn_authors_bugfix(self, git_repo: Path) -> None:
        result = collect_friction(git_repo)
        assert "a.py" in result
        friction = result["a.py"]
        assert isinstance(friction, FileFriction)
        assert friction.distinct_authors_12m == 1
        assert friction.bugfix_commits_12m == 1
        assert friction.churn_commits_90d == 2


class TestInterestScores:
    def test_empty_input(self) -> None:
        assert compute_interest_scores({}) == {}

    def test_percentile_normalized_within_range(self) -> None:
        friction = {
            "hot.py": FileFriction(churn_commits_90d=10, distinct_authors_12m=5, bugfix_commits_12m=3),
            "cold.py": FileFriction(churn_commits_90d=0, distinct_authors_12m=1, bugfix_commits_12m=0),
        }
        scores = compute_interest_scores(friction)
        assert scores["hot.py"] > scores["cold.py"]
        for v in scores.values():
            assert 0.0 <= v <= 1.0


class TestSeverityModulation:
    def test_sleeping_bear_detected_for_zero_activity(self) -> None:
        assert is_sleeping_bear(FileFriction()) is True

    def test_sleeping_bear_false_when_active(self) -> None:
        assert is_sleeping_bear(FileFriction(churn_commits_90d=1)) is False

    def test_sleeping_bear_false_when_none(self) -> None:
        assert is_sleeping_bear(None) is False

    def test_minefield_requires_high_metric_and_activity(self) -> None:
        active = FileFriction(churn_commits_90d=5, bugfix_commits_12m=0)
        assert is_minefield(active, high_metric=True) is True
        assert is_minefield(active, high_metric=False) is False

    def test_minefield_false_when_dormant(self) -> None:
        assert is_minefield(FileFriction(), high_metric=True) is False
