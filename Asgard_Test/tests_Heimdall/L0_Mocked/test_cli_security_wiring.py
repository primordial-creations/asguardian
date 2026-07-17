"""
CLI wiring tests: --scoring pass-through, dispatch-engine routing with
qualitative confidence buckets, .heimdall.yml plumbing, and gate
--diff/--base/--tier flags.
"""

import json

import pytest

from Asgard.Heimdall.cli.main import create_parser
from Asgard.Heimdall.cli.handlers.security import run_security_analysis
from Asgard.Heimdall.cli.handlers._security_dispatch import (
    count_lines_of_code,
    load_heimdall_yml,
    run_dispatch_scan,
)


@pytest.fixture()
def vuln_project(tmp_path):
    (tmp_path / "app.py").write_text(
        "import os\n"
        "import yaml\n\n"
        "def handler(request):\n"
        "    data = yaml.load(request.body)\n"
        "    os.system('echo ' + request.args['cmd'])\n"
        "    return data\n"
    )
    return tmp_path


# ---------------------------------------------------------------- parsing

def test_security_scan_accepts_scoring_flag():
    args = create_parser().parse_args(
        ["security", "scan", ".", "--scoring", "v2"]
    )
    assert args.scoring == "v2"


def test_security_scan_scoring_defaults_to_v1():
    args = create_parser().parse_args(["security", "scan", "."])
    assert args.scoring == "v1"
    assert args.include_test_context is False


def test_gate_accepts_diff_base_tier_flags():
    args = create_parser().parse_args(
        ["gate", ".", "--diff", "--base", "develop", "--tier", "pr"]
    )
    assert args.diff is True
    assert args.base == "develop"
    assert args.tier == "pr"


def test_gate_flags_default_off():
    args = create_parser().parse_args(["gate", "."])
    assert args.diff is False
    assert args.base == "main"
    assert args.tier is None


# ---------------------------------------------------------------- helpers

def test_count_lines_of_code(vuln_project):
    assert count_lines_of_code(vuln_project) == 6


def test_load_heimdall_yml_absent_is_empty(tmp_path):
    assert load_heimdall_yml(tmp_path) == {}


def test_load_heimdall_yml_reads_keys(tmp_path):
    (tmp_path / ".heimdall.yml").write_text(
        "test_context_enabled: false\nstrict_scan_paths:\n  - 'src/auth/.*'\n"
    )
    yml = load_heimdall_yml(tmp_path)
    assert yml["test_context_enabled"] is False
    assert yml["strict_scan_paths"] == ["src/auth/.*"]


def test_dispatch_scan_buckets_and_priority_order(vuln_project):
    entries = run_dispatch_scan(vuln_project)
    assert entries, "expected dispatch findings on the vulnerable fixture"
    buckets = {e["confidence"] for e in entries}
    assert buckets <= {"Certain", "Probable", "Possible", "Unlikely"}
    priorities = [e["priority"] for e in entries]
    assert priorities == sorted(priorities, reverse=True)
    # No raw probabilities are exposed.
    assert all(not isinstance(e["confidence"], float) for e in entries)


def test_dispatch_scan_test_context_filtered_by_default(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_stuff.py").write_text(
        "import pickle\n\ndef test_x():\n    pickle.loads(b'')\n"
    )
    assert run_dispatch_scan(tmp_path) == []
    included = run_dispatch_scan(tmp_path, include_test_context=True)
    assert any(e["rule_id"] == "L2.pickle_load" for e in included)


# ---------------------------------------------------------------- happy path

def test_security_scan_json_carries_scoring_and_dispatch(
    vuln_project, capsys
):
    args = create_parser().parse_args(
        ["security", "scan", str(vuln_project), "--scoring", "v2",
         "--format", "json"]
    )
    code = run_security_analysis(args, analysis_type="all")
    out = capsys.readouterr().out
    payload = json.loads(out[out.find("{"):out.rfind("}") + 1])
    assert payload["scoring"]["version"] == "v2"
    assert payload["scoring"]["total_lines_of_code"] > 0
    assert "security_score_v2" in payload["scoring"]
    assert any(
        e["rule_id"] == "L2.yaml_unsafe_load"
        for e in payload["dispatch_findings"]
    )
    assert code == 1  # findings present
