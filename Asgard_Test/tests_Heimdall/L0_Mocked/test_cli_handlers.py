"""Tests for Asgard._cli_handlers."""
import argparse
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from Asgard._cli_handlers import (
    handle_init,
    handle_init_backend,
    handle_install_browsers,
    handle_setup_hooks,
    COMPREHENSIVE_HELP,
)


def _make_namespace(**kwargs):
    ns = argparse.Namespace()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


class TestCliHandlersInstantiation:
    def test_comprehensive_help_is_string(self):
        assert isinstance(COMPREHENSIVE_HELP, str)
        assert len(COMPREHENSIVE_HELP) > 0


class TestHandleInitCleanPath:
    def test_init_yaml_creates_file(self, tmp_path):
        args = _make_namespace(format="yaml", force=False)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 0
        assert (tmp_path / "asgard.yaml").exists()

    def test_init_toml_creates_file(self, tmp_path):
        args = _make_namespace(format="toml", force=False)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 0
        assert (tmp_path / "pyproject.toml.asguardian").exists()

    def test_init_json_creates_file(self, tmp_path):
        args = _make_namespace(format="json", force=False)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 0
        assert (tmp_path / ".asgardrc").exists()

    def test_init_force_overwrites(self, tmp_path):
        (tmp_path / "asgard.yaml").write_text("old")
        args = _make_namespace(format="yaml", force=True)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 0


class TestHandleInitEdgeCases:
    def test_init_no_force_existing_file_returns_one(self, tmp_path):
        (tmp_path / "asgard.yaml").write_text("existing")
        args = _make_namespace(format="yaml", force=False)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 1

    def test_init_unknown_format_returns_one(self, tmp_path):
        args = _make_namespace(format="xml", force=False)
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = handle_init(args)
        assert result == 1


class TestHandleSetupHooksCleanPath:
    def test_setup_hooks_default_args(self, tmp_path):
        args = _make_namespace(path=str(tmp_path), pre_push=False, vscode=False)
        with patch("Asgard._cli_handlers.setup_hooks", return_value=0) as mock_hooks:
            result = handle_setup_hooks(args)
        assert result == 0
        mock_hooks.assert_called_once_with(
            project_path=tmp_path.resolve(),
            install_pre_push=False,
            setup_vscode=False,
        )

    def test_setup_hooks_pre_push_and_vscode(self, tmp_path):
        args = _make_namespace(path=str(tmp_path), pre_push=True, vscode=True)
        with patch("Asgard._cli_handlers.setup_hooks", return_value=0) as mock_hooks:
            result = handle_setup_hooks(args)
        assert result == 0
        _, kwargs = mock_hooks.call_args
        assert kwargs["install_pre_push"] is True
        assert kwargs["setup_vscode"] is True


class TestHandleInitBackendCleanPath:
    def test_init_backend_delegates_to_service(self):
        args = _make_namespace(folder_name="my_service")
        with patch("Asgard._cli_handlers.init_backend", return_value=0) as mock_init:
            result = handle_init_backend(args)
        assert result == 0
        mock_init.assert_called_once_with("my_service")


class TestHandleInstallBrowsersCleanPath:
    def test_install_browsers_success(self):
        args = _make_namespace(browsers=["chromium"])
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = handle_install_browsers(args)
        assert result == 0

    def test_install_browsers_multiple(self):
        args = _make_namespace(browsers=["chromium", "firefox"])
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = handle_install_browsers(args)
        assert result == 0
        called_cmd = mock_run.call_args[0][0]
        assert "chromium" in called_cmd
        assert "firefox" in called_cmd

    def test_install_browsers_not_found(self):
        args = _make_namespace(browsers=["chromium"])
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = handle_install_browsers(args)
        assert result == 1

    def test_install_browsers_failure_code_propagated(self):
        args = _make_namespace(browsers=["chromium"])
        mock_result = MagicMock()
        mock_result.returncode = 127
        with patch("subprocess.run", return_value=mock_result):
            result = handle_install_browsers(args)
        assert result == 127
