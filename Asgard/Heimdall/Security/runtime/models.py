"""
Runtime observation schema (WS7 -- Runtime/IAST hook interface).

A ``RuntimeObservation`` is a single, portable record of a source -> sink
event actually seen at runtime by *some* language-specific runtime agent
(Node async-hooks, Python sys.settrace/import hooks, a Java agent, ...).
None of those agents are implemented here -- this module is the interface
they would emit into, plus an offline replay loader for testing/CI.

Design constraints (see ASGARD_UPLIFT_GOAL.md and
_Docs/Planning/TaintGaps/00_Plan.md WS7):
  * No live instrumentation and no network calls in this module.
  * Library code never calls ``time.time()``/``datetime.now()`` itself --
    timestamps are passed in by the caller (the runtime agent), keeping
    this module deterministic and testable.
  * Runtime proof is *stronger* than a static guess: a matching runtime
    observation may RAISE a static finding's confidence (mark it
    ``confirmed_at_runtime``), but the ABSENCE of a runtime observation
    must never be used to downgrade or drop a static finding -- the
    runtime agent may simply not have exercised that code path.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintSinkType,
    TaintSourceType,
)


class RuntimeConfidence(str, Enum):
    """Epistemic status of a runtime observation.

    ``confirmed_at_runtime`` is the strong signal: the runtime agent
    actually watched tainted data reach the sink during execution.
    ``suspected`` is reserved for lower-fidelity runtime signals (e.g. a
    heuristic hook that saw a plausible but not fully-traced flow) and
    must never be treated as equivalent proof.
    """
    CONFIRMED_AT_RUNTIME = "confirmed_at_runtime"
    SUSPECTED = "suspected"


class RuntimeObservation(BaseModel):
    """A single source -> sink event observed at runtime.

    Fields deliberately mirror ``TaintFlow``'s source/sink typing so a
    runtime observation can be matched against (and merged with) static
    ``TaintFlow`` findings without a lossy translation layer.
    """

    source_type: TaintSourceType = Field(
        ..., description="Type of taint source observed (e.g. http_parameter)"
    )
    source_file: str = Field(..., description="File path where the tainted value entered")
    source_line: int = Field(0, ge=0, description="Line number of the source (0 = unknown)")

    sink_type: TaintSinkType = Field(
        ..., description="Type of taint sink the value reached (e.g. sql_query)"
    )
    sink_file: str = Field(..., description="File path where the sink was invoked")
    sink_line: int = Field(..., ge=0, description="Line number of the sink invocation")

    tainted_value_fingerprint: str = Field(
        ...,
        description=(
            "Non-reversible fingerprint (e.g. hash) of the tainted value "
            "observed at the sink. Never the raw value -- this schema must "
            "not leak sensitive runtime data into reports."
        ),
    )
    trace_id: str = Field(
        ..., description="Stack/trace id correlating this observation to a single execution"
    )
    stack_frames: List[str] = Field(
        default_factory=list,
        description="Optional call-stack frames (function names) from source to sink",
    )

    timestamp_in: float = Field(
        ...,
        description=(
            "Unix epoch seconds when the observation was recorded, supplied "
            "by the calling runtime agent. This library never calls "
            "time.time()/datetime.now() itself -- timestamps are always "
            "passed in, keeping ingestion deterministic and replayable."
        ),
    )

    confidence_marker: RuntimeConfidence = Field(
        RuntimeConfidence.CONFIRMED_AT_RUNTIME,
        description="Epistemic status of this observation (see RuntimeConfidence)",
    )

    cwe_id: str = Field("", description="CWE ID for this class of vulnerability, if known")
    agent: str = Field(
        "",
        description="Identifier of the runtime agent that emitted this observation (e.g. 'node-asynchooks-v1')",
    )
    language: str = Field("", description="Source language of the observed process, if known")

    class Config:
        use_enum_values = True

    @model_validator(mode="after")
    def _non_empty_paths(self) -> "RuntimeObservation":
        if not self.sink_file.strip():
            raise ValueError("sink_file must not be empty")
        if not self.tainted_value_fingerprint.strip():
            raise ValueError("tainted_value_fingerprint must not be empty")
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be empty")
        return self


class RuntimeObservationBatch(BaseModel):
    """A portable container for a batch of runtime observations.

    This is the JSON/JSONL-serializable envelope a runtime agent would
    write out, and what the offline ingestion loader reads back in. Kept
    separate from ``RuntimeObservation`` itself so a bare JSON array of
    observations (no envelope) is also accepted by the loader.
    """

    schema_version: str = Field("1.0", description="Schema version of this batch")
    generated_by: str = Field("", description="Identifier of the producing runtime agent")
    observations: List[RuntimeObservation] = Field(default_factory=list)
