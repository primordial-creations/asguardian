"""
Unified `asguardian` wrapper passthrough tests.

The top-level CLI must pass module-global flags (e.g. `forseti --format
sarif ...`) through to module CLIs verbatim, while keeping every existing
top-level command (init, --version, bare help) working.
"""

import json

import pytest

from Asgard.cli import main as asgard_main


def test_bare_invocation_prints_help_and_returns_zero(capsys):
    assert asgard_main([]) == 0
    out = capsys.readouterr().out
    assert "asguardian" in out


def test_version_flag_still_works():
    with pytest.raises(SystemExit) as exc:
        asgard_main(["--version"])
    assert exc.value.code == 0


def test_forseti_global_flag_passthrough_sarif(tmp_path, capsys):
    spec = tmp_path / "openapi.yaml"
    spec.write_text(
        "openapi: 3.0.0\n"
        "info:\n  title: T\n  version: '1.0'\n"
        "paths:\n  /x:\n    get:\n      responses:\n        '200':\n"
        "          description: ok\n"
    )
    code = asgard_main(
        ["forseti", "--format", "sarif", "openapi", "validate", str(spec)]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["version"] == "2.1.0"
    assert "runs" in payload
    assert isinstance(code, int)


def test_module_version_passthrough_returns_zero():
    # Module CLIs that sys.exit() are absorbed into a plain return code.
    assert asgard_main(["heimdall", "--version"]) == 0


def test_unknown_module_still_errors():
    with pytest.raises(SystemExit):
        asgard_main(["notamodule", "whatever"])
