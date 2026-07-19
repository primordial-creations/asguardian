"""
Offline ingestion + merge for runtime observations (WS7).

Two entry points:

  * ``load_observations`` / ``load_observations_from_file`` -- read a
    portable JSON or JSONL file of ``RuntimeObservation`` records (or a
    ``RuntimeObservationBatch`` envelope) into memory. Pure file I/O plus
    validation -- no network, no live instrumentation.
  * ``merge_runtime_observations`` -- merge a list of observations into a
    static ``TaintReport``:
      (a) a runtime observation that MATCHES an existing static
          ``TaintFlow`` marks that flow ``confirmed_at_runtime`` (raising
          it out of the "possible/needs-review" bucket -- runtime proof is
          strictly stronger than a static guess), and
      (b) a runtime observation with NO static match is added as a new
          ``TaintFlow`` labeled ``origin="runtime"`` -- these are the
          dynamic-dispatch/reflection paths static analysis could not see.

Matching is by (sink_file, sink_line, sink_type), with a tolerant fallback
that also accepts (sink_file, sink_type, cwe_id) when the exact line
doesn't line up (e.g. the static engine reports the call-site line while
the runtime agent reports the resolved-frame line for a wrapped call).

Absence of a runtime observation for a static finding is NEVER used to
downgrade or drop that finding -- the runtime agent may simply not have
exercised that code path during the observed run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Union

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    SanitizerRecord,
    TaintFlow,
    TaintFlowStep,
    TaintReport,
)
from Asgard.Heimdall.Security.runtime.models import (
    RuntimeConfidence,
    RuntimeObservation,
    RuntimeObservationBatch,
)


def load_observations(raw_text: str) -> List[RuntimeObservation]:
    """Parse a JSON or JSONL blob of runtime observations.

    Accepts three shapes:
      1. A ``RuntimeObservationBatch`` JSON object (``{"observations": [...]}``).
      2. A bare JSON array of observation objects.
      3. JSONL -- one observation object per line.
    """
    stripped = raw_text.strip()
    if not stripped:
        return []

    # Try whole-document JSON first (batch envelope or bare array).
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        if isinstance(parsed, dict) and "observations" in parsed:
            batch = RuntimeObservationBatch.model_validate(parsed)
            return list(batch.observations)
        if isinstance(parsed, list):
            return [RuntimeObservation.model_validate(item) for item in parsed]
        if isinstance(parsed, dict):
            # A single observation object.
            return [RuntimeObservation.model_validate(parsed)]

    # Fall back to JSONL: one observation per non-empty line.
    observations: List[RuntimeObservation] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        observations.append(RuntimeObservation.model_validate(json.loads(line)))
    return observations


def load_observations_from_file(path: Union[str, Path]) -> List[RuntimeObservation]:
    """Read and parse a JSON/JSONL file of runtime observations from disk."""
    file_path = Path(path)
    return load_observations(file_path.read_text(encoding="utf-8"))


def _sink_type_value(flow_or_obs) -> str:
    sink_type = flow_or_obs.sink_type
    return sink_type.value if hasattr(sink_type, "value") else str(sink_type)


def _matches(flow: TaintFlow, obs: RuntimeObservation) -> bool:
    """Tolerant match between a static TaintFlow and a runtime observation."""
    flow_sink_type = _sink_type_value(flow)
    obs_sink_type = _sink_type_value(obs)

    same_file = flow.sink_location.file_path == obs.sink_file
    same_type = flow_sink_type == obs_sink_type

    if not (same_file and same_type):
        return False

    # Exact line match is the strong case.
    if flow.sink_location.line_number == obs.sink_line:
        return True

    # Tolerant fallback: same file + sink type + matching CWE (when both
    # sides have one), for cases where reported line numbers diverge
    # (e.g. static reports the call expression, runtime reports the
    # resolved-frame line of a wrapper).
    if flow.cwe_id and obs.cwe_id and flow.cwe_id == obs.cwe_id:
        return True

    return False


def _observation_to_runtime_flow(obs: RuntimeObservation) -> TaintFlow:
    """Build a new runtime-only TaintFlow for an observation with no static match."""
    source_step = TaintFlowStep(
        file_path=obs.source_file,
        line_number=obs.source_line,
        function_name=obs.stack_frames[0] if obs.stack_frames else "",
        step_type="source",
        code_snippet="",
        variable_name="",
    )
    sink_step = TaintFlowStep(
        file_path=obs.sink_file,
        line_number=obs.sink_line,
        function_name=obs.stack_frames[-1] if obs.stack_frames else "",
        step_type="sink",
        code_snippet="",
        variable_name="",
    )
    intermediate_steps = [
        TaintFlowStep(
            file_path=obs.sink_file,
            line_number=0,
            function_name=frame,
            step_type="propagation",
            code_snippet="",
            variable_name="",
        )
        for frame in obs.stack_frames[1:-1]
    ] if len(obs.stack_frames) > 2 else []

    is_confirmed = obs.confidence_marker in (
        RuntimeConfidence.CONFIRMED_AT_RUNTIME,
        RuntimeConfidence.CONFIRMED_AT_RUNTIME.value,
    )

    return TaintFlow(
        source_type=obs.source_type,
        sink_type=obs.sink_type,
        # Runtime-only findings are surfaced at "high" by default: they were
        # actually observed reaching the sink, but static severity modeling
        # (which weighs sanitizer/context evidence) never ran on this path.
        # A human/CI policy can re-tier by CWE; we do not silently downgrade.
        severity="high",
        confidence=1.0 if is_confirmed else 0.5,
        confidence_bucket="certain" if is_confirmed else "possible",
        hop_count=max(len(obs.stack_frames) - 1, 0),
        sanitizers_applied=[],
        source_location=source_step,
        sink_location=sink_step,
        intermediate_steps=intermediate_steps,
        title=f"Runtime-observed {_sink_type_value(obs)} flow (no static match)",
        description=(
            "This flow was observed directly at runtime "
            f"(trace_id={obs.trace_id}, agent={obs.agent or 'unknown'}) but has no "
            "corresponding static finding -- likely a dynamic-dispatch, "
            "reflection, or otherwise dynamically-resolved path that static "
            "taint analysis cannot see. Runtime proof is direct evidence of "
            "an exploitable flow."
        ),
        cwe_id=obs.cwe_id,
        owasp_category="",
        sanitizers_present=False,
        origin="runtime",
        confirmed_at_runtime=is_confirmed,
        runtime_trace_ids=[obs.trace_id],
    )


def merge_runtime_observations(
    static_report: TaintReport,
    observations: Iterable[RuntimeObservation],
) -> TaintReport:
    """Merge runtime observations into a static TaintReport.

    Returns a NEW TaintReport (the input is not mutated) with:
      (a) matching static flows marked ``confirmed_at_runtime=True`` and
          their ``runtime_trace_ids`` extended, and
      (b) unmatched observations appended as new ``origin="runtime"`` flows.

    Static findings with no matching observation are carried over UNCHANGED
    -- absence of a runtime observation is never treated as evidence the
    flow is safe.
    """
    observations = list(observations)

    merged = static_report.model_copy(deep=True)
    matched_obs_indices: set = set()

    for flow in merged.flows:
        for idx, obs in enumerate(observations):
            if idx in matched_obs_indices:
                continue
            if _matches(flow, obs):
                flow.confirmed_at_runtime = True
                if obs.trace_id not in flow.runtime_trace_ids:
                    flow.runtime_trace_ids.append(obs.trace_id)
                matched_obs_indices.add(idx)
                # A flow may be confirmed by multiple observations; keep
                # scanning remaining observations for other matches to this
                # same flow, but don't let one observation match twice.

    new_flows: List[TaintFlow] = []
    for idx, obs in enumerate(observations):
        if idx in matched_obs_indices:
            continue
        new_flows.append(_observation_to_runtime_flow(obs))

    for flow in new_flows:
        merged.add_flow(flow)

    return merged
