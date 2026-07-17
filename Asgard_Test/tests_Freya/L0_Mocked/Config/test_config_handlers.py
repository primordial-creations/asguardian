"""L0 tests: Freya CLI config handlers (config init/show/validate)."""

import argparse

import pytest

from Asgard.Freya.cli._handlers_config import (
    run_config_init,
    run_config_show,
    run_config_validate,
)


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _args(config=None):
    return argparse.Namespace(config=config)


class TestConfigInit:
    def test_writes_freyarc(self, isolated_cwd, capsys):
        exit_code = run_config_init(_args(), verbose=False)
        assert exit_code == 0
        assert (isolated_cwd / ".freyarc").exists()
        out = capsys.readouterr().out
        assert ".freyarc" in out

    def test_custom_path(self, isolated_cwd):
        target = str(isolated_cwd / "my.freyarc")
        exit_code = run_config_init(_args(config=target), verbose=False)
        assert exit_code == 0
        assert (isolated_cwd / "my.freyarc").exists()


class TestConfigShow:
    def test_show_defaults(self, isolated_cwd, capsys):
        exit_code = run_config_show(_args(), verbose=False)
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "wcag_level: AA (default)" in out
        assert "Config source: default" in out

    def test_show_annotates_file_source(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\n")
        exit_code = run_config_show(_args(), verbose=False)
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "wcag_level: AAA (from .freyarc)" in out
        assert "Config source: from .freyarc" in out

    def test_show_missing_explicit_path_errors(self, isolated_cwd, capsys):
        exit_code = run_config_show(_args(config=str(isolated_cwd / "nope.yaml")), verbose=False)
        assert exit_code == 1
        assert "Error" in capsys.readouterr().out

    def test_show_invalid_config_errors(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text("categories: {bad: true}\n")
        exit_code = run_config_show(_args(), verbose=False)
        assert exit_code == 1
        assert "Error" in capsys.readouterr().out

    def test_show_crawl_section_when_present(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text(
            "crawl:\n  start_url: https://example.com\n  concurrency: 6\n"
        )
        exit_code = run_config_show(_args(), verbose=False)
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "crawl.concurrency: 6" in out

    def test_show_no_crawl_section(self, isolated_cwd, capsys):
        exit_code = run_config_show(_args(), verbose=False)
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "crawl: (not configured)" in out


class TestConfigValidate:
    def test_validate_no_file_is_valid(self, isolated_cwd, capsys):
        exit_code = run_config_validate(_args(), verbose=False)
        assert exit_code == 0
        assert "No config file found" in capsys.readouterr().out

    def test_validate_good_file(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\n")
        exit_code = run_config_validate(_args(), verbose=False)
        assert exit_code == 0
        assert "Configuration valid" in capsys.readouterr().out

    def test_validate_bad_yaml(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text("wcag_level: [unterminated\n")
        exit_code = run_config_validate(_args(), verbose=False)
        assert exit_code == 1
        assert "Invalid configuration" in capsys.readouterr().out

    def test_validate_bad_schema_reports_field_errors(self, isolated_cwd, capsys):
        (isolated_cwd / ".freyarc").write_text("categories: {bad: true}\n")
        exit_code = run_config_validate(_args(), verbose=False)
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "categories" in out

    def test_validate_missing_explicit_path(self, isolated_cwd, capsys):
        exit_code = run_config_validate(_args(config=str(isolated_cwd / "nope.yaml")), verbose=False)
        assert exit_code == 1
        assert "Error" in capsys.readouterr().out
