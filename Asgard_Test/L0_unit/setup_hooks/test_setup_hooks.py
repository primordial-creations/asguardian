"""
L0 Unit Tests for the HooksSetup service.

Tests cover setup_hooks() and write_vscode_config() using mocks and tmp_path
so no real git or pre-commit processes are spawned and no real FS is polluted.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from Asgard.HooksSetup.service import setup_hooks, write_vscode_config


# ---------------------------------------------------------------------------
# setup_hooks – missing git repo
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestSetupHooksNoGitRepo:
    def test_returns_1_when_not_a_git_repo(self, tmp_path):
        result = setup_hooks(project_path=tmp_path)
        assert result == 1


# ---------------------------------------------------------------------------
# setup_hooks – pre-commit not installed
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestSetupHooksPrecommitMissing:
    def test_returns_1_when_precommit_not_found(self, tmp_path):
        (tmp_path / ".git").mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = setup_hooks(project_path=tmp_path)

        assert result == 1


# ---------------------------------------------------------------------------
# setup_hooks – commit hook only (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestSetupHooksCommitOnly:
    def test_installs_commit_hook_and_returns_0(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = setup_hooks(project_path=tmp_path)

        assert result == 0
        mock_run.assert_called_once_with(
            ["pre-commit", "install"],
            cwd=tmp_path,
            check=False,
        )

    def test_returns_nonzero_when_hook_install_fails(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=2)
        with patch("subprocess.run", return_value=mock_result):
            result = setup_hooks(project_path=tmp_path)

        assert result == 2


# ---------------------------------------------------------------------------
# setup_hooks – pre-push flag
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestSetupHooksPrePush:
    def test_installs_both_hooks_when_pre_push_set(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = setup_hooks(project_path=tmp_path, install_pre_push=True)

        assert result == 0
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0] == call(
            ["pre-commit", "install"],
            cwd=tmp_path,
            check=False,
        )
        assert mock_run.call_args_list[1] == call(
            ["pre-commit", "install", "--hook-type", "pre-push"],
            cwd=tmp_path,
            check=False,
        )

    def test_stops_after_commit_hook_fails_when_pre_push_set(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = setup_hooks(project_path=tmp_path, install_pre_push=True)

        assert result == 1
        assert mock_run.call_count == 1  # aborted after commit hook failure

    def test_pre_push_hook_missing_precommit_returns_1(self, tmp_path):
        (tmp_path / ".git").mkdir()

        ok = MagicMock(returncode=0)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [ok, FileNotFoundError()]
            result = setup_hooks(project_path=tmp_path, install_pre_push=True)

        assert result == 1


# ---------------------------------------------------------------------------
# setup_hooks – --vscode flag
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestSetupHooksVsCode:
    def test_creates_vscode_files_when_flag_set(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = setup_hooks(project_path=tmp_path, setup_vscode=True)

        assert result == 0
        assert (tmp_path / ".vscode" / "settings.json").exists()
        assert (tmp_path / ".vscode" / "extensions.json").exists()

    def test_does_not_create_vscode_files_without_flag(self, tmp_path):
        (tmp_path / ".git").mkdir()

        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            setup_hooks(project_path=tmp_path, setup_vscode=False)

        assert not (tmp_path / ".vscode").exists()


# ---------------------------------------------------------------------------
# write_vscode_config – settings content
# ---------------------------------------------------------------------------


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
class TestWriteVsCodeConfig:
    def test_creates_vscode_directory(self, tmp_path):
        write_vscode_config(tmp_path)
        assert (tmp_path / ".vscode").is_dir()

    def test_settings_json_has_format_on_save(self, tmp_path):
        write_vscode_config(tmp_path)
        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        assert settings["editor.formatOnSave"] is True

    def test_settings_json_sets_ruff_as_formatter(self, tmp_path):
        write_vscode_config(tmp_path)
        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        assert settings["[python]"]["editor.defaultFormatter"] == "charliermarsh.ruff"

    def test_settings_json_includes_ruff_fix_all(self, tmp_path):
        write_vscode_config(tmp_path)
        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        actions = settings["[python]"]["editor.codeActionsOnSave"]
        assert actions["source.fixAll.ruff"] == "explicit"

    def test_settings_json_includes_ruff_organize_imports(self, tmp_path):
        write_vscode_config(tmp_path)
        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        actions = settings["[python]"]["editor.codeActionsOnSave"]
        assert actions["source.organizeImports.ruff"] == "explicit"

    def test_extensions_json_recommends_ruff(self, tmp_path):
        write_vscode_config(tmp_path)
        ext = json.loads((tmp_path / ".vscode" / "extensions.json").read_text())
        assert "charliermarsh.ruff" in ext["recommendations"]

    def test_extensions_json_recommends_mypy(self, tmp_path):
        write_vscode_config(tmp_path)
        ext = json.loads((tmp_path / ".vscode" / "extensions.json").read_text())
        assert "ms-python.mypy-type-checker" in ext["recommendations"]

    def test_extensions_json_recommends_python_extension(self, tmp_path):
        write_vscode_config(tmp_path)
        ext = json.loads((tmp_path / ".vscode" / "extensions.json").read_text())
        assert "ms-python.python" in ext["recommendations"]

    def test_merges_with_existing_settings(self, tmp_path):
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        existing = {"my.custom.setting": True, "editor.tabSize": 4}
        (vscode_dir / "settings.json").write_text(json.dumps(existing))

        write_vscode_config(tmp_path)

        settings = json.loads((vscode_dir / "settings.json").read_text())
        assert settings["my.custom.setting"] is True
        assert settings["editor.tabSize"] == 4
        assert settings["editor.formatOnSave"] is True

    def test_merges_with_existing_extensions(self, tmp_path):
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        existing = {"recommendations": ["ms-vscode.cpptools"]}
        (vscode_dir / "extensions.json").write_text(json.dumps(existing))

        write_vscode_config(tmp_path)

        ext = json.loads((vscode_dir / "extensions.json").read_text())
        recs = ext["recommendations"]
        assert "ms-vscode.cpptools" in recs
        assert "charliermarsh.ruff" in recs

    def test_does_not_duplicate_existing_recommendations(self, tmp_path):
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        existing = {"recommendations": ["charliermarsh.ruff"]}
        (vscode_dir / "extensions.json").write_text(json.dumps(existing))

        write_vscode_config(tmp_path)

        ext = json.loads((vscode_dir / "extensions.json").read_text())
        assert ext["recommendations"].count("charliermarsh.ruff") == 1

    def test_returns_0(self, tmp_path):
        assert write_vscode_config(tmp_path) == 0
