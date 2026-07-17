"""
Tests for Heimdall full-scan profile gating and report output location.

The GAIA house-rule checks (lazy imports, env-var fallbacks) must NOT run in
the default scan path; they are opt-in via --profile gaia. HTML reports must
not be written to the current working directory by default.
"""

import argparse

import pytest

from Asgard.Heimdall.cli.handlers._base import _report_file_path
from Asgard.Heimdall.cli.handlers.scan import run_full_scan
from Asgard.Heimdall.cli.handlers.scan_steps_1_6 import GAIA_HOUSE_RULE_CATEGORIES
from Asgard.Heimdall.cli.main import create_parser


@pytest.fixture
def sample_project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "mod.py").write_text(
        'import os\n\n\ndef f():\n    import json\n    return json.dumps(os.getenv("X", "y"))\n'
    )
    return project


def _scan_args(path, **overrides):
    parser = create_parser()
    argv = ["scan", str(path)]
    return parser.parse_args(argv + overrides.pop("extra", []))


class TestScanProfileGating:
    def test_default_scan_excludes_house_rules(self, sample_project, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        args = _scan_args(sample_project)
        run_full_scan(args, verbose=False)
        out = capsys.readouterr().out
        assert "Lazy Import" not in out
        assert "Fallback Detection" not in out
        for cat in GAIA_HOUSE_RULE_CATEGORIES:
            assert cat not in out

    def test_default_profile_is_general(self, sample_project):
        args = _scan_args(sample_project)
        assert args.profile == "general"

    def test_gaia_profile_includes_house_rules(self, sample_project, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        args = _scan_args(sample_project, extra=["--profile", "gaia"])
        run_full_scan(args, verbose=False)
        out = capsys.readouterr().out
        assert "Lazy Import Detection" in out
        assert "Environment Variable Fallback Detection" in out
        # The sample project has one lazy import and one env fallback.
        assert "Lazy Imports" in out
        assert "Env Fallbacks" in out

    def test_unknown_profile_rejected(self, sample_project):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["scan", str(sample_project), "--profile", "acme"])


class TestReportOutputLocation:
    def test_default_report_dir_is_contained(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("HEIMDALL_REPORT_DIR", raising=False)
        path = _report_file_path()
        assert path.parent == tmp_path / ".asgard" / "reports"
        assert path.name.startswith("heimdall_report_")
        assert path.suffix == ".html"

    def test_explicit_output_dir_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HEIMDALL_REPORT_DIR", str(tmp_path / "envdir"))
        target = tmp_path / "explicit"
        path = _report_file_path(output_dir=target)
        assert path.parent == target

    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HEIMDALL_REPORT_DIR", str(tmp_path / "envdir"))
        path = _report_file_path()
        assert path.parent == tmp_path / "envdir"

    def test_scan_writes_no_html_into_cwd(self, sample_project, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("HEIMDALL_REPORT_DIR", raising=False)
        args = _scan_args(sample_project)
        run_full_scan(args, verbose=False)
        capsys.readouterr()
        assert not list(tmp_path.glob("heimdall_report_*.html"))
        reports = list((tmp_path / ".asgard" / "reports").glob("heimdall_report_*.html"))
        assert len(reports) == 1

    def test_scan_respects_output_flag(self, sample_project, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        out_dir = tmp_path / "myreports"
        args = _scan_args(sample_project, extra=["--output", str(out_dir)])
        run_full_scan(args, verbose=False)
        capsys.readouterr()
        assert list(out_dir.glob("heimdall_report_*.html"))
        assert not list(tmp_path.glob("heimdall_report_*.html"))
