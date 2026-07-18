"""
CLI wiring tests for the new Verdandi subcommands:
web cwv-assess, slo burn-rate-policy, cache warmup, db pool-signature.
"""

import json
import random
from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.cli import main as verdandi_main
from Asgard.Verdandi.cli._parser import create_parser


def _run(argv):
    with pytest.raises(SystemExit) as exc:
        verdandi_main(argv)
    return exc.value.code


# ---------------------------------------------------------------- parsing

def test_parser_accepts_cwv_assess():
    args = create_parser().parse_args(["web", "cwv-assess", "m.json"])
    assert args.web_command == "cwv-assess"
    assert args.metrics_file == "m.json"


def test_parser_accepts_burn_rate_policy():
    args = create_parser().parse_args(
        ["slo", "burn-rate-policy", "m.json", "--target", "99.5",
         "--at", "2026-01-01T00:00:00"]
    )
    assert args.slo_command == "burn-rate-policy"
    assert args.target == 99.5


def test_parser_accepts_cache_warmup_and_pool_signature():
    args = create_parser().parse_args(["cache", "warmup", "b.json"])
    assert args.cache_command == "warmup"
    args = create_parser().parse_args(["db", "pool-signature", "l.json"])
    assert args.db_command == "pool-signature"


# ---------------------------------------------------------------- happy paths

def test_cwv_assess_passing_page(tmp_path, capsys):
    random.seed(7)
    payload = {
        "lcp": [random.gauss(2000, 300) for _ in range(150)],
        "inp": [random.gauss(120, 30) for _ in range(150)],
        "cls": [abs(random.gauss(0.04, 0.02)) for _ in range(150)],
    }
    f = tmp_path / "cwv.json"
    f.write_text(json.dumps(payload))
    code = _run(["web", "cwv-assess", str(f)])
    out = capsys.readouterr().out
    assert "Core Web Vitals: PASS" in out
    assert code == 0


def test_cwv_assess_json_output(tmp_path, capsys):
    payload = {"lcp": [1000.0] * 60}
    f = tmp_path / "cwv.json"
    f.write_text(json.dumps(payload))
    _run(["--format", "json", "web", "cwv-assess", str(f)])
    data = json.loads(capsys.readouterr().out)
    assert data["lcp"]["rating"] == "good"
    assert data["core_passing"] is None  # inp/cls missing: undetermined


def test_cache_warmup_warming(tmp_path, capsys):
    buckets = [
        {"hits": 900, "misses": 100},
        {"hits": 500, "misses": 500},
        {"hits": 650, "misses": 350},
        {"hits": 780, "misses": 220},
    ]
    f = tmp_path / "warm.json"
    f.write_text(json.dumps(buckets))
    code = _run(["cache", "warmup", str(f)])
    assert "warming" in capsys.readouterr().out.lower()
    assert code == 0


def test_pool_signature_detects_exhaustion(tmp_path, capsys):
    random.seed(3)
    latencies = (
        [random.gauss(10, 2) for _ in range(300)]
        + [random.gauss(110, 2.2) for _ in range(300)]
    )
    f = tmp_path / "lat.json"
    f.write_text(json.dumps(latencies))
    code = _run(["db", "pool-signature", str(f)])
    out = capsys.readouterr().out
    assert "pool_exhaustion" in out
    assert code == 1


def test_burn_rate_policy_fires_on_heavy_burn(tmp_path, capsys):
    now = datetime(2026, 7, 17, 12, 0, 0)
    metrics = [
        {
            "timestamp": (now - timedelta(minutes=5 * i)).isoformat(),
            "good_events": 9000,
            "total_events": 10000,
        }
        for i in range(1000)
    ]
    f = tmp_path / "slo.json"
    f.write_text(json.dumps({
        "slo": {"name": "api", "type": "availability", "target": 99.9},
        "metrics": metrics,
    }))
    code = _run(
        ["slo", "burn-rate-policy", str(f), "--at", now.isoformat()]
    )
    out = capsys.readouterr().out
    assert "FIRED" in out
    assert code == 1


def test_missing_file_errors_cleanly(capsys):
    code = _run(["cache", "warmup", "/nonexistent/x.json"])
    assert code == 1
    assert "not found" in capsys.readouterr().out.lower()
