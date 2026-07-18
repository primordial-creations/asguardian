"""
CLI handler for the `eval` command group: exposes Heimdall's evaluation
harness (Asgard/Heimdall/evaluation/) as `heimdall eval run`.

The harness is a pure measurement layer over scanner output -- it never
modifies scanner behavior. This wiring is additive CLI surface only.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional


def _load_json(path: str) -> Optional[Any]:
    file_path = Path(path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Could not parse JSON from {file_path}: {e}")
        return None


def run_eval(args: argparse.Namespace, verbose: bool = False) -> int:
    """`heimdall eval run <corpus.json>`.

    Input: {"findings": [{file_path, line, cwe, confidence, sink_node_id?,
            rule_id?}, ...], "ground_truth": [{id, file_path, cwe, span:
            {file_path, start_line, end_line, start_col?, end_col?},
            source?}, ...], "total_loc": int, "fallback": 3?}
    """
    from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
    from Asgard.Heimdall.evaluation.spans import ASTSpan
    from Asgard.Heimdall.evaluation.runner import run_corpus

    data = _load_json(args.input_file)
    if data is None:
        return 1
    if not isinstance(data, dict) or "total_loc" not in data:
        print(
            "Error: Expected a JSON object with 'findings', 'ground_truth', "
            "and 'total_loc'."
        )
        return 1

    try:
        findings = [
            ReportedFinding(
                file_path=f["file_path"],
                line=int(f["line"]),
                cwe=f["cwe"],
                confidence=float(f["confidence"]),
                sink_node_id=f.get("sink_node_id", ""),
                rule_id=f.get("rule_id", ""),
                raw=f.get("raw"),
            )
            for f in data.get("findings", [])
        ]
        ground_truth = [
            GroundTruthInstance(
                id=g["id"],
                file_path=g["file_path"],
                cwe=g["cwe"],
                span=ASTSpan(
                    file_path=g["span"]["file_path"],
                    start_line=int(g["span"]["start_line"]),
                    end_line=int(g["span"]["end_line"]),
                    start_col=int(g["span"].get("start_col", 0)),
                    end_col=int(g["span"].get("end_col", 0)),
                ),
                source=g.get("source", "fixture"),
            )
            for g in data.get("ground_truth", [])
        ]
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error: Invalid eval corpus input: {e}")
        return 1

    metrics = run_corpus(
        findings, ground_truth,
        total_loc=int(data["total_loc"]),
        fallback=int(data.get("fallback", 3)),
    )

    gate_result = None
    gate_profile = getattr(args, "gate_profile", None)
    if gate_profile:
        from Asgard.Heimdall.evaluation.gate import evaluate_gate
        gate_result = evaluate_gate(metrics, profile=gate_profile)

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        payload = {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f_half": metrics.f_half,
            "f_two": metrics.f_two,
            "alert_density": metrics.alert_density,
            "total_loc": metrics.total_loc,
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
        }
        if gate_result is not None:
            payload["gate"] = asdict(gate_result)
        print(json.dumps(payload, indent=2, default=str))
    else:
        lines = ["", "HEIMDALL EVALUATION HARNESS", "=" * 60,
                 f"  Precision:     {metrics.precision:.3f}",
                 f"  Recall:        {metrics.recall:.3f}",
                 f"  F-0.5:         {metrics.f_half:.3f}",
                 f"  F-2:           {metrics.f_two:.3f}",
                 f"  Alert density: {metrics.alert_density:.2f} FP/10k LOC",
                 f"  TP/FP/FN:      {metrics.tp}/{metrics.fp}/{metrics.fn}"]
        if gate_result is not None:
            lines.append(f"  Gate ({gate_profile}): {'PASS' if gate_result.passed else 'FAIL'}")
            for reason in gate_result.reasons:
                lines.append(f"    - {reason}")
        print("\n".join(lines))

    if gate_result is not None:
        return 0 if gate_result.passed else 1
    return 0
