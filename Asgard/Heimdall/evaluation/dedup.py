"""
Semantic-instance dedup (plan 10 s2 / plan 04 dedup parity).

Multiple raw alerts (e.g. several tainted paths converging on one sink)
must collapse to a single true positive when scored, matching the
dedup key plan 04 already uses for reporting: ``(file, sink, cwe)``. The
sink identity is ``sink_node_id`` when the scanner supplied one (AST
node id / stable key); it falls back to the reported line number, which
is coarser but still collapses same-line duplicate alerts.
"""

from typing import Dict, List, Tuple

from Asgard.Heimdall.evaluation.corpus import ReportedFinding


def _dedup_key(f: ReportedFinding) -> Tuple[str, str, str]:
    sink = f.sink_node_id or str(f.line)
    return (f.file_path, sink, f.cwe)


def dedup_findings(findings: List[ReportedFinding]) -> List[ReportedFinding]:
    """Collapse findings sharing ``(file, sink, cwe)`` to one instance,
    keeping the highest-confidence representative (the engine's own best
    estimate for that semantic instance)."""
    best: Dict[Tuple[str, str, str], ReportedFinding] = {}
    for f in findings:
        key = _dedup_key(f)
        current = best.get(key)
        if current is None or f.confidence > current.confidence:
            best[key] = f
    return list(best.values())
