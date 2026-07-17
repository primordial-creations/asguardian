"""
Coordinated-Omission Toolkit

Closed-loop load generators and in-process timers systematically drop the
samples that matter most: while a slow request is in flight, the requests
that SHOULD have been issued (and would have queued behind it) are never
measured. Percentiles computed from such data are optimistic lies
(RESEARCH_14, Gil Tene).

This module provides:
- HDR-style expected-interval backfill correction
- The Tene heuristic for detecting suspect datasets
- A Little's-law sanity check for impossible throughput/latency reports
- A one-call analyzer that returns machine-readable quality flags
"""

import math
from typing import List, NamedTuple, Optional, Sequence

#: Quality flag: dataset statistics suggest coordinated omission occurred.
SUSPECT_COORDINATED_OMISSION = "SUSPECT_COORDINATED_OMISSION"
#: Quality flag: reported throughput x latency exceeds possible concurrency.
LITTLES_LAW_VIOLATION = "LITTLES_LAW_VIOLATION"
#: Quality flag: percentiles were computed from backfill-corrected samples.
CO_CORRECTED = "CO_CORRECTED"


def correct_expected_interval(
    samples_ms: Sequence[float],
    expected_interval_ms: float,
) -> List[float]:
    """
    HDR-histogram-style expected-interval backfill.

    For each recorded sample s longer than the expected inter-request
    interval, synthesize the latencies of the requests that were blocked
    behind it: s - i*interval for i = 1, 2, ... while the result is still
    greater than the interval. A 100 ms sample at a 1 ms expected interval
    backfills 99, 98, ..., 2 ms (matching HDR's
    recordValueWithExpectedInterval semantics).

    Args:
        samples_ms: Recorded latency samples in milliseconds
        expected_interval_ms: Intended inter-request interval
            (1000 / target_throughput_rps)

    Returns:
        New list containing the original samples plus backfilled samples.
    """
    if expected_interval_ms <= 0:
        return list(samples_ms)

    corrected: List[float] = []
    for sample in samples_ms:
        corrected.append(sample)
        if sample <= expected_interval_ms:
            continue
        backfill = sample - expected_interval_ms
        while backfill >= expected_interval_ms:
            corrected.append(backfill)
            backfill -= expected_interval_ms
    return corrected


def tene_heuristic(avg_ms: float, max_ms: float, duration_ms: float) -> bool:
    """
    Gil Tene's coordinated-omission smell test.

    If a single observed max-latency stall had been fully sampled, the
    stalled requests alone would contribute ~max^2 / (2 * duration) to the
    average. When the reported average is BELOW that floor, the dataset
    cannot have recorded the queueing behind the stall:
    suspect coordinated omission when avg < max^2 / (2 * duration).

    Returns:
        True when the dataset is suspect.
    """
    if duration_ms <= 0 or max_ms <= 0:
        return False
    return avg_ms < (max_ms ** 2) / (2.0 * duration_ms)


def littles_law_check(
    throughput_rps: float,
    avg_latency_s: float,
    max_concurrency: float,
) -> bool:
    """
    Little's-law sanity check: L = lambda * W.

    The average number of requests in flight implied by the report is
    throughput * avg latency; if that exceeds the configured maximum
    concurrency, the report is physically impossible (bad measurement,
    typically coordinated omission or a wrong clock).

    Returns:
        True when the report is CONSISTENT (valid); False when impossible.
    """
    if max_concurrency <= 0:
        return False
    implied_concurrency = throughput_rps * avg_latency_s
    return implied_concurrency <= max_concurrency


class CoordinatedOmissionReport(NamedTuple):
    """Result of a coordinated-omission quality analysis."""

    suspect: bool
    quality_flags: List[str]
    corrected_samples_ms: Optional[List[float]]
    implied_concurrency: Optional[float]


def analyze(
    samples_ms: Sequence[float],
    duration_ms: float,
    expected_interval_ms: Optional[float] = None,
    throughput_rps: Optional[float] = None,
    max_concurrency: Optional[float] = None,
    apply_correction: bool = False,
) -> CoordinatedOmissionReport:
    """
    Run all applicable coordinated-omission checks on a latency dataset.

    Args:
        samples_ms: Recorded latency samples in milliseconds
        duration_ms: Total measurement duration in milliseconds
        expected_interval_ms: Intended inter-request interval; enables
            backfill correction when apply_correction=True
        throughput_rps: Reported throughput; enables the Little's-law check
        max_concurrency: Configured client/server concurrency bound
        apply_correction: If True (and expected_interval_ms given), return
            backfill-corrected samples

    Returns:
        CoordinatedOmissionReport with quality flags suitable for attaching
        to PercentileResult.quality_flags.
    """
    flags: List[str] = []
    corrected: Optional[List[float]] = None
    implied: Optional[float] = None

    if samples_ms and duration_ms > 0:
        avg = sum(samples_ms) / len(samples_ms)
        peak = max(samples_ms)
        if tene_heuristic(avg, peak, duration_ms):
            flags.append(SUSPECT_COORDINATED_OMISSION)

        if throughput_rps is not None and max_concurrency is not None:
            implied = throughput_rps * (avg / 1000.0)
            if not littles_law_check(throughput_rps, avg / 1000.0, max_concurrency):
                flags.append(LITTLES_LAW_VIOLATION)

    if apply_correction and expected_interval_ms and expected_interval_ms > 0:
        corrected = correct_expected_interval(samples_ms, expected_interval_ms)
        if len(corrected) > len(samples_ms):
            flags.append(CO_CORRECTED)

    return CoordinatedOmissionReport(
        suspect=SUSPECT_COORDINATED_OMISSION in flags
        or LITTLES_LAW_VIOLATION in flags,
        quality_flags=flags,
        corrected_samples_ms=corrected,
        implied_concurrency=implied,
    )
