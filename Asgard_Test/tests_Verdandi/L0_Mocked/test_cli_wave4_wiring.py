"""
CLI-level tests for the Wave-4 cross-module wiring: system/network groups
(brand-new), and extended db/slo/cache/analyze subcommands.

Mirrors the pattern in test_cli_new_apis.py: real small JSON fixtures on
disk, invoked through the real `main()` entry point, asserting on the
parsed args, exit code, and stdout text/JSON.
"""

import json

import pytest

from Asgard.Verdandi.cli import main as verdandi_main
from Asgard.Verdandi.cli._parser import create_parser


def _run(argv):
    with pytest.raises(SystemExit) as exc:
        verdandi_main(argv)
    return exc.value.code


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argv,dest,expected", [
    (["system", "psi", "f.json"], "system_command", "psi"),
    (["system", "throttle", "f.json"], "system_command", "throttle"),
    (["system", "correlate", "f.json"], "system_command", "correlate"),
    (["network", "phases", "f.json"], "network_command", "phases"),
    (["network", "use", "f.json"], "network_command", "use"),
    (["network", "signature", "f.json"], "network_command", "signature"),
    (["db", "budget", "f.json"], "db_command", "budget"),
    (["db", "queries", "f.json"], "db_command", "queries"),
    (["slo", "portfolio", "f.json"], "slo_command", "portfolio"),
    (["slo", "budget-policy", "f.json"], "slo_command", "budget-policy"),
    (["slo", "dynamic-budget", "f.json"], "slo_command", "dynamic-budget"),
    (["analyze", "self-slo", "f.json"], "analyze_command", "self-slo"),
    (["cache", "stampede", "f.json"], "cache_command", "stampede"),
])
def test_parser_accepts_new_subcommands(argv, dest, expected):
    args = create_parser().parse_args(argv)
    assert getattr(args, dest) == expected


def test_db_queries_per_class_flag_parses():
    args = create_parser().parse_args(
        ["db", "queries", "f.json", "--per-class", "--slow-threshold", "50"]
    )
    assert args.per_class is True
    assert args.slow_threshold == 50


# ---------------------------------------------------------------------------
# Happy-path invocations (existing behavior unchanged; additive only)
# ---------------------------------------------------------------------------

def test_system_psi_happy_path(tmp_path, capsys):
    f = tmp_path / "psi.json"
    f.write_text(json.dumps({
        "snapshot": {
            "resource": "cpu",
            "some_avg10": 0.5, "some_avg60": 0.2, "some_avg300": 0.1,
            "full_avg10": 0.0, "full_avg60": 0.0, "full_avg300": 0.0,
        }
    }))
    code = _run(["system", "psi", str(f)])
    out = capsys.readouterr().out
    assert "PSI" in out
    assert code == 0


def test_system_throttle_happy_path(tmp_path, capsys):
    f = tmp_path / "throttle.json"
    f.write_text(json.dumps({
        "cpu_quota_us": 100000, "cpu_period_us": 100000,
        "nr_periods": 100, "nr_throttled": 40,
        "throttled_time_ns": 20_000_000_000, "usage_ns": 90_000_000_000,
    }))
    code = _run(["system", "throttle", str(f)])
    out = capsys.readouterr().out
    assert "THROTTLE" in out
    assert code in (0, 1)


def test_network_phases_happy_path(tmp_path, capsys):
    f = tmp_path / "phases.json"
    f.write_text(json.dumps([
        {"dns_ms": 5, "tcp_ms": 10, "tls_ms": 20, "request_ms": 2, "response_ms": 50},
    ]))
    code = _run(["network", "phases", str(f)])
    out = capsys.readouterr().out
    assert "NETWORK CONNECTION-PHASE" in out
    assert code == 0


def test_network_missing_file_errors_cleanly(capsys):
    code = _run(["network", "use", "/nonexistent/path/does-not-exist.json"])
    out = capsys.readouterr().out
    assert "Error" in out
    assert code == 1


def test_db_queries_per_class_json_output(tmp_path, capsys):
    f = tmp_path / "queries.json"
    f.write_text(json.dumps([
        {"query_type": "select", "execution_time_ms": 12.0,
         "query_text": "SELECT * FROM a WHERE id=1"},
        {"query_type": "select", "execution_time_ms": 14.0,
         "query_text": "SELECT * FROM a WHERE id=2"},
    ]))
    code = _run(["--format", "json", "db", "queries", str(f), "--per-class"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert payload[0]["count"] == 2
    assert code == 0


def test_slo_portfolio_cxi_only(tmp_path, capsys):
    f = tmp_path / "portfolio.json"
    f.write_text(json.dumps({
        "journey_success_rates": {"checkout": 0.995, "login": 0.999}
    }))
    code = _run(["slo", "portfolio", str(f)])
    out = capsys.readouterr().out
    assert "PORTFOLIO" in out
    assert code == 0


def test_analyze_self_slo_happy_path(tmp_path, capsys):
    f = tmp_path / "run.json"
    f.write_text(json.dumps({
        "entities_submitted": 100, "entities_scored": 100,
        "valid_rejections": 0, "entities_failed": 0,
        "run_started": "2026-07-17T00:00:00",
        "data_closed_at": "2026-07-17T01:00:00",
        "report_ready_at": "2026-07-17T01:05:00",
    }))
    code = _run(["analyze", "self-slo", str(f)])
    out = capsys.readouterr().out
    assert "ANALYTICAL YIELD" in out
    assert code == 0


def test_cache_stampede_happy_path(tmp_path, capsys):
    f = tmp_path / "stampede.json"
    f.write_text(json.dumps([
        {"key": "k1", "t": 1.0, "hit": True},
        {"key": "k1", "t": 1.1, "hit": False, "recompute_ms": 50},
    ]))
    code = _run(["cache", "stampede", str(f)])
    out = capsys.readouterr().out
    assert "STAMPEDE" in out
    assert code == 0


# ---------------------------------------------------------------------------
# Existing CLI surface unaffected (regression guard)
# ---------------------------------------------------------------------------

def test_existing_pool_signature_command_still_works(tmp_path, capsys):
    f = tmp_path / "latencies.json"
    f.write_text(json.dumps([10, 12, 11, 200, 210, 205]))
    code = _run(["db", "pool-signature", str(f)])
    out = capsys.readouterr().out
    assert "POOL-EXHAUSTION" in out
    assert code in (0, 1)
