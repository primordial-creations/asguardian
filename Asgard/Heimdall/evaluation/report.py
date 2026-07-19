"""
Human-readable + JSON rendering for corpus metrics and gate results
(plan 10 "Concrete Changes": report.py).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from Asgard.Heimdall.evaluation.calibration import ReliabilityBin, brier_score
from Asgard.Heimdall.evaluation.gate import GateResult
from Asgard.Heimdall.evaluation.runner import CorpusMetrics


def metrics_to_dict(metrics: CorpusMetrics, corpus_label: Optional[str] = None) -> Dict[str, Any]:
    brier = brier_score(metrics.calibration_records)
    d: Dict[str, Any] = {
        "tp": metrics.tp,
        "fp": metrics.fp,
        "fn": metrics.fn,
        "total_loc": metrics.total_loc,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f_0.5": metrics.f_half,
        "f_2": metrics.f_two,
        "alert_density_per_10k_loc": metrics.alert_density,
        "brier_score": brier,
    }
    if corpus_label:
        d["corpus_label"] = corpus_label
    return d


def render_text_report(
    metrics: CorpusMetrics,
    gate: Optional[GateResult] = None,
    reliability: Optional[List[ReliabilityBin]] = None,
    corpus_label: Optional[str] = None,
) -> str:
    lines: List[str] = []
    lines.append("Heimdall evaluation report")
    lines.append("=" * 27)
    if corpus_label:
        lines.append(f"Corpus: {corpus_label}")
    d = metrics_to_dict(metrics, corpus_label=corpus_label)
    lines.append(f"TP={d['tp']}  FP={d['fp']}  FN={d['fn']}  LOC={d['total_loc']}")
    lines.append(f"precision={d['precision']:.3f}  recall={d['recall']:.3f}")
    lines.append(f"F0.5={d['f_0.5']:.3f}  F2={d['f_2']:.3f}")
    lines.append(f"alert density = {d['alert_density_per_10k_loc']:.2f} FP/10k LOC")
    lines.append(f"Brier score = {d['brier_score']:.4f}")

    if reliability:
        lines.append("")
        lines.append("Reliability diagram (predicted vs. empirical TP rate):")
        for b in reliability:
            lines.append(
                f"  [{b.lower:.1f}, {b.upper:.1f}) n={b.count:4d}  "
                f"predicted={b.predicted_mean:.3f}  empirical={b.empirical_rate:.3f}"
            )

    if gate is not None:
        lines.append("")
        status = "PASS" if gate.passed else "FAIL"
        lines.append(f"Gate: {status}")
        for reason in gate.reasons:
            lines.append(f"  - {reason}")

    return "\n".join(lines)


def render_json_report(
    metrics: CorpusMetrics,
    gate: Optional[GateResult] = None,
    corpus_label: Optional[str] = None,
) -> str:
    payload: Dict[str, Any] = {"metrics": metrics_to_dict(metrics, corpus_label=corpus_label)}
    if gate is not None:
        payload["gate"] = {"passed": gate.passed, "reasons": gate.reasons}
    return json.dumps(payload, indent=2, sort_keys=True)
