"""
Corpus runner (plan 10 "Concrete Changes": scan -> dedup -> AST-bbox
match -> metrics). The runner does not invoke scanners itself -- callers
scan and adapt findings (see ``corpus.finding_from_vulnerability`` /
``finding_from_taint_flow``), keeping this package additive/read-only
with respect to the analyzers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
from Asgard.Heimdall.evaluation.dedup import dedup_findings
from Asgard.Heimdall.evaluation.metrics import (
    MatchResult,
    match_findings,
    precision,
    recall,
    f_beta,
    alert_density,
)


@dataclass
class CorpusMetrics:
    match: MatchResult
    total_loc: int
    precision: float
    recall: float
    f_half: float  # F-0.5 (profile A: CI/developer)
    f_two: float  # F-2 (profile B: async audit)
    alert_density: float  # FP per 10k LOC
    calibration_records: List[Tuple[float, bool]] = field(default_factory=list)

    @property
    def tp(self) -> int:
        return self.match.tp

    @property
    def fp(self) -> int:
        return self.match.fp

    @property
    def fn(self) -> int:
        return self.match.fn


def run_corpus(
    findings: Sequence[ReportedFinding],
    ground_truth: Sequence[GroundTruthInstance],
    total_loc: int,
    fallback: int = 3,
) -> CorpusMetrics:
    """Run the full plan-10 pipeline over one corpus scan:
    dedup -> AST-bbox match -> precision/recall/F-beta/alert-density, and
    collect ``(raw_confidence, is_tp)`` records for calibration.
    """
    deduped = dedup_findings(list(findings))
    match = match_findings(deduped, list(ground_truth), fallback=fallback)

    p = precision(match.tp, match.fp)
    r = recall(match.tp, match.fn)
    f_half = f_beta(p, r, beta=0.5)
    f_two = f_beta(p, r, beta=2.0)
    density = alert_density(match.fp, total_loc)

    records: List[Tuple[float, bool]] = [(f.confidence, True) for f in match.true_positives]
    records += [(f.confidence, False) for f in match.false_positives]

    return CorpusMetrics(
        match=match,
        total_loc=total_loc,
        precision=p,
        recall=r,
        f_half=f_half,
        f_two=f_two,
        alert_density=density,
        calibration_records=records,
    )
