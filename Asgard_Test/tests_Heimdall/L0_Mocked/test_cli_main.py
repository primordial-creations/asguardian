"""Tests for Asgard.cli.main()."""
import pytest
from unittest.mock import MagicMock, patch

from Asgard.cli import main


class TestCliMainInstantiation:
    def test_main_is_callable(self):
        assert callable(main)


class TestCliMainCleanPath:
    def test_no_args_returns_zero(self, capsys):
        result = main([])
        assert result == 0

    def test_help_all_returns_zero(self, capsys):
        result = main(["--help-all"])
        assert result == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_init_yaml_creates_file(self, tmp_path):
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = main(["init", "--format", "yaml"])
        assert result == 0
        assert (tmp_path / "asgard.yaml").exists()

    def test_init_json_creates_file(self, tmp_path):
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = main(["init", "--format", "json"])
        assert result == 0
        assert (tmp_path / ".asgardrc").exists()

    def test_install_browsers_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = main(["install-browsers", "chromium"])
        assert result == 0
        mock_run.assert_called_once()

    def test_setup_hooks_delegates_to_service(self, tmp_path):
        with patch("Asgard._cli_handlers.setup_hooks", return_value=0) as mock_hooks:
            result = main(["setup-hooks", "--path", str(tmp_path)])
        assert result == 0
        mock_hooks.assert_called_once()

    def test_heimdall_delegates_to_heimdall_main(self):
        with patch("Asgard.cli.heimdall_main", return_value=0) as mock_h:
            result = main(["heimdall", "analyze", "."])
        assert result == 0
        mock_h.assert_called_once()

    def test_freya_delegates_to_freya_main(self):
        with patch("Asgard.cli.freya_main", return_value=0) as mock_f:
            result = main(["freya", "crawl", "http://localhost"])
        assert result == 0
        mock_f.assert_called_once()

    def test_forseti_delegates_to_forseti_main(self):
        with patch("Asgard.cli.forseti_main", return_value=0) as mock_f:
            result = main(["forseti", "validate", "spec.yaml"])
        assert result == 0
        mock_f.assert_called_once()

    def test_verdandi_delegates_to_verdandi_main(self):
        with patch("Asgard.cli.verdandi_main", return_value=0) as mock_v:
            result = main(["verdandi", "report", "."])
        assert result == 0
        mock_v.assert_called_once()

    def test_volundr_delegates_to_volundr_main(self):
        with patch("Asgard.cli.volundr_main", return_value=0) as mock_v:
            result = main(["volundr", "generate", "kubernetes"])
        assert result == 0
        mock_v.assert_called_once()


class TestCliMainEdgeCases:
    def test_init_existing_file_no_force_returns_one(self, tmp_path):
        (tmp_path / "asgard.yaml").write_text("existing")
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = main(["init", "--format", "yaml"])
        assert result == 1

    def test_init_existing_file_force_overwrites(self, tmp_path):
        (tmp_path / "asgard.yaml").write_text("old")
        with patch("Asgard._cli_handlers.Path.cwd", return_value=tmp_path):
            result = main(["init", "--format", "yaml", "--force"])
        assert result == 0

    def test_install_browsers_playwright_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = main(["install-browsers"])
        assert result == 1

    def test_install_browsers_failure_code_propagated(self):
        mock_result = MagicMock()
        mock_result.returncode = 2
        with patch("subprocess.run", return_value=mock_result):
            result = main(["install-browsers", "firefox"])
        assert result == 2
