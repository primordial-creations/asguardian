"""
Causal Trace Normalizer

A trace is a lossy chronological record of uncoordinated schedulers, not a
clean DAG (DEEPTHINK_06). This module runs three independently-testable,
pure passes over a parsed trace's spans, each correcting a specific
instrument artifact and emitting an epistemic confidence flag (never an
alert) when it makes a non-trivial correction:

1. Orphan adoption — re-parents spans with a missing/unknown
   ``parent_span_id`` onto the tightest ancestor whose window fully bounds
   them (falls back to the trace root).
2. Clock-skew correction — for cross-host client/server RPC pairs, shifts
   the server span (and all its descendants) by the estimated clock offset,
   using the standard symmetric-RTT NTP-style formula.
3. Async truncation — top-down pass setting each span's
   ``effective_end_ns = min(span.end, parent.effective_end)`` so
   fire-and-forget async children can no longer hijack the critical path.

Each pass is a pure function: ``List[TraceSpan] -> (List[TraceSpan], List[str])``.
The orchestrator ``normalize_trace`` runs them in order (orphan adoption ->
clock skew -> async truncation) and returns a normalized
``DistributedTrace`` plus the union of flags raised, plus a fixed list of
documented assumptions the pipeline relies on.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from Asgard.Verdandi.Tracing.models.tracing_models import (
    ConfidenceFlag,
    DistributedTrace,
    TraceSpan,
)

# Flags surfaced above this magnitude / condition.
HEAVY_SKEW_THRESHOLD_MS = 50.0
SEVERE_TRUNCATION_RATIO = 0.25

NORMALIZATION_ASSUMPTIONS: List[str] = [
    "Symmetric network latency is assumed for clock-skew correction "
    "(client-to-server transit == server-to-client transit).",
    "Wait-state assumption: an active child span implies the parent is "
    "blocked on it (used by the sweep-line critical path, not this module).",
    "An async child that happens to finish before its parent is "
    "indistinguishable from a synchronous child using span timing alone.",
]


def _build_children(spans: List[TraceSpan]) -> Dict[str, List[TraceSpan]]:
    children: Dict[str, List[TraceSpan]] = defaultdict(list)
    for s in spans:
        if s.parent_span_id:
            children[s.parent_span_id].append(s)
    return children


def _collect_subtree_ids(root_id: str, children: Dict[str, List[TraceSpan]]) -> List[str]:
    ids = [root_id]
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            ids.append(child.span_id)
            stack.append(child.span_id)
    return ids


def adopt_orphans(spans: List[TraceSpan]) -> Tuple[List[TraceSpan], List[ConfidenceFlag]]:
    """
    Re-parent spans with a missing/unknown ``parent_span_id`` onto the
    tightest ancestor whose ``[start, end]`` fully bounds them; fall back to
    the trace root when no bounding span exists.

    Returns (possibly-updated spans, flags). Pure function; does not mutate
    its input.
    """
    span_list = list(spans)
    if not span_list:
        return span_list, []

    by_id = {s.span_id: s for s in span_list}
    flags: List[ConfidenceFlag] = []

    root = next((s for s in span_list if s.parent_span_id is None), None)
    if root is None:
        root = min(span_list, key=lambda s: s.start_time_unix_nano)

    updated: List[TraceSpan] = []
    for s in span_list:
        is_orphan = s.span_id != root.span_id and (
            s.parent_span_id is None or s.parent_span_id not in by_id
        )
        if not is_orphan:
            updated.append(s)
            continue

        candidates = [
            c
            for c in span_list
            if c.span_id != s.span_id
            and c.start_time_unix_nano <= s.start_time_unix_nano
            and c.end_time_unix_nano >= s.end_time_unix_nano
        ]
        if candidates:
            tightest = max(candidates, key=lambda c: c.start_time_unix_nano)
            new_parent_id = tightest.span_id
        else:
            new_parent_id = root.span_id

        if new_parent_id != s.parent_span_id:
            s = s.model_copy(update={"parent_span_id": new_parent_id})
            flags.append(ConfidenceFlag.ORPHANED_SUBTREE_RECOVERED)
        updated.append(s)

    return updated, flags


def correct_clock_skew(spans: List[TraceSpan]) -> Tuple[List[TraceSpan], List[ConfidenceFlag]]:
    """
    For each cross-host client/server RPC pair (a SERVER span whose parent
    is a CLIENT span in a different service), compute:

        transit = ((client_end - client_start) - (server_end - server_start)) / 2
        offset = (client_start + transit) - server_start

    and shift the server span *and all its descendants* by ``offset`` (this
    preserves local ordering within the server-side subtree).

    Flags ``HEAVY_CLOCK_SKEW_ADJUSTED`` when ``|offset| > 50ms`` or the
    computed transit is negative (server span claims to have run "faster
    than light" relative to the client's observed round trip).
    """
    span_list = list(spans)
    if not span_list:
        return span_list, []

    by_id = {s.span_id: s for s in span_list}
    children = _build_children(span_list)
    flags: List[ConfidenceFlag] = []
    offsets_ns: Dict[str, int] = {}

    for s in span_list:
        if s.kind != "SERVER" or not s.parent_span_id:
            continue
        client = by_id.get(s.parent_span_id)
        if client is None or client.kind != "CLIENT":
            continue
        if client.service_name == s.service_name:
            continue  # not cross-host

        client_dur_ns = client.end_time_unix_nano - client.start_time_unix_nano
        server_dur_ns = s.end_time_unix_nano - s.start_time_unix_nano
        transit_ns = (client_dur_ns - server_dur_ns) / 2
        offset_ns = (client.start_time_unix_nano + transit_ns) - s.start_time_unix_nano

        if abs(offset_ns) >= 1:
            for sid in _collect_subtree_ids(s.span_id, children):
                offsets_ns[sid] = offsets_ns.get(sid, 0) + int(round(offset_ns))

        if abs(offset_ns / 1e6) > HEAVY_SKEW_THRESHOLD_MS or transit_ns < 0:
            flags.append(ConfidenceFlag.HEAVY_CLOCK_SKEW_ADJUSTED)

    if not offsets_ns:
        return span_list, flags

    updated: List[TraceSpan] = []
    for s in span_list:
        offset = offsets_ns.get(s.span_id)
        if offset:
            s = s.model_copy(
                update={
                    "start_time_unix_nano": s.start_time_unix_nano + offset,
                    "end_time_unix_nano": s.end_time_unix_nano + offset,
                }
            )
        updated.append(s)

    return updated, flags


def truncate_async(spans: List[TraceSpan]) -> Tuple[List[TraceSpan], List[ConfidenceFlag]]:
    """
    Top-down pass: ``span.effective_end = min(span.end, parent.effective_end)``.

    Flags ``SEVERE_ASYNC_TRUNCATION`` when the truncated duration exceeds
    25% of the child's raw duration (a fire-and-forget async child that
    would otherwise dominate the critical path).
    """
    span_list = list(spans)
    if not span_list:
        return span_list, []

    by_id = {s.span_id: s for s in span_list}
    children = _build_children(span_list)
    flags: List[ConfidenceFlag] = []
    effective_end: Dict[str, int] = {}

    roots = [
        s for s in span_list if s.parent_span_id is None or s.parent_span_id not in by_id
    ]
    for r in roots:
        effective_end[r.span_id] = r.end_time_unix_nano

    queue: List[str] = [r.span_id for r in roots]
    while queue:
        parent_id = queue.pop(0)
        parent_eff_end = effective_end[parent_id]
        for child in children.get(parent_id, []):
            new_end = min(child.end_time_unix_nano, parent_eff_end)
            effective_end[child.span_id] = new_end

            truncated_ns = child.end_time_unix_nano - new_end
            raw_duration_ns = child.end_time_unix_nano - child.start_time_unix_nano
            if raw_duration_ns > 0 and truncated_ns > SEVERE_TRUNCATION_RATIO * raw_duration_ns:
                flags.append(ConfidenceFlag.SEVERE_ASYNC_TRUNCATION)

            queue.append(child.span_id)

    updated: List[TraceSpan] = []
    for s in span_list:
        eff = effective_end.get(s.span_id, s.end_time_unix_nano)
        if eff != s.effective_end_ns:
            s = s.model_copy(update={"effective_end_ns": eff})
        updated.append(s)

    return updated, flags


def normalize_trace(
    trace: DistributedTrace,
) -> Tuple[DistributedTrace, List[ConfidenceFlag], List[str]]:
    """
    Run the full causal normalization pipeline (orphan adoption -> clock
    skew -> async truncation) over a trace's spans.

    Returns (normalized_trace, flags, assumptions). ``normalized_trace`` is
    a new ``DistributedTrace`` with the same aggregate metadata as the
    input, but with a normalized ``spans`` list (and ``root_span`` updated
    to point at the corresponding normalized span instance).
    """
    spans = list(trace.spans)
    all_flags: List[ConfidenceFlag] = []

    spans, flags = adopt_orphans(spans)
    all_flags.extend(flags)

    spans, flags = correct_clock_skew(spans)
    all_flags.extend(flags)

    spans, flags = truncate_async(spans)
    all_flags.extend(flags)

    new_root: Optional[TraceSpan] = None
    if trace.root_span is not None:
        new_root = next(
            (s for s in spans if s.span_id == trace.root_span.span_id), trace.root_span
        )
    else:
        new_root = next((s for s in spans if s.parent_span_id is None), None)

    normalized = trace.model_copy(update={"spans": spans, "root_span": new_root})

    # De-duplicate flags while preserving first-seen order.
    seen = set()
    deduped_flags: List[ConfidenceFlag] = []
    for f in all_flags:
        if f not in seen:
            seen.add(f)
            deduped_flags.append(f)

    return normalized, deduped_flags, list(NORMALIZATION_ASSUMPTIONS)
