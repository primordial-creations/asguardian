"""Exercise declared console callables without building/installing the package."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
ALIASES = {
    "asgard": "asguardian",
    "asgard-dashboard": "asguardian-dashboard",
    "asgard-mcp": "asguardian-mcp",
}
LAUNCH = """
from importlib.metadata import EntryPoint
import sys
name, target, *arguments = sys.argv[1:]
sys.argv = [name, *arguments]
sys.exit(EntryPoint(name=name, value=target, group='console_scripts').load()())
"""


def run_entrypoint(name, arguments, cwd):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-c", LAUNCH, name, SCRIPTS[name], *arguments],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_compatibility_aliases_preserve_existing_entrypoints():
    expected = {
        "asguardian": "Asgard.cli:main",
        "asguardian-dashboard": "Asgard.Dashboard.server:main",
        "asguardian-mcp": "Asgard.MCP.server:main",
    }
    for name, target in expected.items():
        assert SCRIPTS[name] == target
    for alias, canonical in ALIASES.items():
        assert SCRIPTS[alias] == SCRIPTS[canonical]


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_declared_entrypoint_help_loads_real_callable(name, tmp_path):
    result = run_entrypoint(name, ["--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert ALIASES.get(name, name) in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", [*ALIASES, *ALIASES.values()])
def test_unknown_argument_fails_before_server_or_analyzer_start(name, tmp_path):
    result = run_entrypoint(name, ["--unsupported-cli-contract-option"], tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "--unsupported-cli-contract-option" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["asguardian", "asgard"])
def test_unified_entrypoint_forwards_module_arguments(name, tmp_path):
    result = run_entrypoint(name, ["heimdall", "quality", "rust-audit", "--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "rust-audit" in result.stdout
    assert "--format" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["asguardian", "asgard"])
def test_alias_exposes_versioned_hercules_scan_protocol(name, tmp_path):
    result = run_entrypoint(name, ["scan", "--help"], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "hercules-l13/v1" in result.stdout
    assert "--target" in result.stdout
    assert "--output" in result.stdout
    assert "--severity" in result.stdout
    assert "--exclude" not in result.stdout
    assert not list(tmp_path.iterdir())
