"""
Spatial matching + precision/recall/F-beta/alert-density (plan 10 s2).

Matching is a greedy bipartite assignment: each ground-truth instance
takes at most one reported finding and vice versa, so that N reports
inside one GT span cannot be double-counted as N true positives (that
would already be handled by dedup, but matching stays defensive).
Findings whose CWE does not match any GT instance in the same file are
never matched, even if the line falls inside a span for a different CWE
-- matching plan 10's "(sink, cwe)" identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
from Asgard.Heimdall.evaluation.spans import spans_overlap, DEFAULT_LINE_FALLBACK


@dataclass
class MatchResult:
    true_positives: List[ReportedFinding] = field(default_factory=list)
    false_positives: List[ReportedFinding] = field(default_factory=list)
    false_negatives: List[GroundTruthInstance] = field(default_factory=list)

    @property
    def tp(self) -> int:
        return len(self.true_positives)

    @property
    def fp(self) -> int:
        return len(self.false_positives)

    @property
    def fn(self) -> int:
        return len(self.false_negatives)


def match_findings(
    findings: List[ReportedFinding],
    ground_truth: List[GroundTruthInstance],
    fallback: int = DEFAULT_LINE_FALLBACK,
) -> MatchResult:
    """Greedily match deduplicated findings against ground truth by AST
    bounding-box overlap (CWE-scoped). Call after ``dedup_findings``."""
    unmatched_gt = list(ground_truth)
    result = MatchResult()

    for f in findings:
        match_idx = None
        best_distance = None
        for idx, gt in enumerate(unmatched_gt):
            if gt.cwe and f.cwe and gt.cwe != f.cwe:
                continue
            if not spans_overlap(gt.span, f.file_path, f.line, fallback=fallback):
                continue
            distance = gt.span.distance_to_line(f.line)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                match_idx = idx
        if match_idx is not None:
            unmatched_gt.pop(match_idx)
            result.true_positives.append(f)
        else:
            result.false_positives.append(f)

    result.false_negatives = unmatched_gt
    return result


def precision(tp: int, fp: int) -> float:
    denom = tp + fp
    return tp / denom if denom else 1.0


def recall(tp: int, fn: int) -> float:
    denom = tp + fn
    return tp / denom if denom else 1.0


def f_beta(p: float, r: float, beta: float) -> float:
    """F-beta score; 0.0 when both precision and recall are 0."""
    b2 = beta * beta
    denom = (b2 * p) + r
    if denom == 0:
        return 0.0
    return (1 + b2) * (p * r) / denom


def alert_density(fp_count: int, total_loc: int) -> float:
    """False positives per 10k LOC (plan 10 s2)."""
    if total_loc <= 0:
        return 0.0
    return fp_count * 10_000.0 / total_loc
