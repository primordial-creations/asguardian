"""
CLI-level tests for the Wave-4 cross-module wiring on Heimdall:

- `oop cohesion --explain <Class>` (Bragi cir_metrics.explain_class)
- `calibrate run` (Bragi Calibration/services/local_calibrator.py)
- `validate-rules` (Bragi Calibration/services/rule_validator.py)
- `eval run` (Heimdall evaluation/ harness)

Uses the real `main()` entry point against small on-disk JSON fixtures,
matching the style of test_cli_main.py / test_cli_handlers.py.
"""

import json

import pytest

from Asgard.Heimdall.cli.main import create_parser, main as heimdall_main


def _run(argv):
    with pytest.raises(SystemExit) as exc:
        heimdall_main(argv)
    return exc.value.code


def test_parser_accepts_calibrate_run():
    args = create_parser().parse_args(["calibrate", "run", "f.json"])
    assert args.calibrate_command == "run"


def test_parser_accepts_validate_rules():
    args = create_parser().parse_args(["validate-rules", "f.json"])
    assert args.command == "validate-rules"


def test_parser_accepts_eval_run():
    args = create_parser().parse_args(["eval", "run", "f.json"])
    assert args.eval_command == "run"


def test_oop_cohesion_explain_flag_parses():
    args = create_parser().parse_args(
        ["oop", "cohesion", ".", "--explain", "MyClass"]
    )
    assert args.explain == "MyClass"


def test_oop_cohesion_explain_missing_class_reports_error(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "empty.js").write_text("// nothing here\n")
    code = _run(["oop", "cohesion", str(src), "--explain", "NoSuchClass"])
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "Error" in out
    assert code == 1


def test_calibrate_run_happy_path(tmp_path, capsys):
    f = tmp_path / "calibrate.json"
    f.write_text(json.dumps({
        "language": "python",
        "metric_samples": {"complexity": list(range(1, 11))},
        "anchor_profile": {
            "language": "python",
            "thresholds": {"complexity": {"warn": 10, "fail": 20}},
        },
        "min_sample_size": 5,
    }))
    code = _run(["calibrate", "run", str(f)])
    out = capsys.readouterr().out
    assert "CALIBRATION" in out
    assert code == 0


def test_calibrate_run_refuses_on_small_sample(tmp_path, capsys):
    f = tmp_path / "calibrate_small.json"
    f.write_text(json.dumps({
        "language": "python",
        "metric_samples": {"complexity": [1, 2]},
        "anchor_profile": {
            "language": "python",
            "thresholds": {"complexity": {"warn": 10, "fail": 20}},
        },
        "min_sample_size": 5,
    }))
    code = _run(["calibrate", "run", str(f)])
    out = capsys.readouterr().out
    assert "Refused:     True" in out
    assert code == 1


def test_validate_rules_happy_path(tmp_path, capsys):
    f = tmp_path / "rules.json"
    f.write_text(json.dumps({
        "rule_id": "R1",
        "observations": [
            {"file_path": "a.py", "loc": 100, "violation_count": 2,
             "touched_by_bugfix": True},
            {"file_path": "b.py", "loc": 100, "violation_count": 0,
             "touched_by_bugfix": False},
        ],
    }))
    code = _run(["validate-rules", str(f)])
    out = capsys.readouterr().out
    assert "RULE VALIDITY" in out
    assert code == 0


def test_eval_run_happy_path(tmp_path, capsys):
    f = tmp_path / "eval.json"
    f.write_text(json.dumps({
        "findings": [
            {"file_path": "a.py", "line": 10, "cwe": "CWE-89", "confidence": 0.9},
        ],
        "ground_truth": [
            {"id": "g1", "file_path": "a.py", "cwe": "CWE-89",
             "span": {"file_path": "a.py", "start_line": 8, "end_line": 12}},
        ],
        "total_loc": 1000,
    }))
    code = _run(["eval", "run", str(f)])
    out = capsys.readouterr().out
    assert "EVALUATION HARNESS" in out
    assert "Precision" in out
    assert code == 0


def test_eval_run_missing_file_errors_cleanly(capsys):
    code = _run(["eval", "run", "/nonexistent/does-not-exist.json"])
    out = capsys.readouterr().out
    assert "Error" in out
    assert code == 1
