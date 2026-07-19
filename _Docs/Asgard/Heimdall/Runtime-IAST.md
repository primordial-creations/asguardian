# Runtime / IAST Hook Interface (WS7)

## Status

**Interface + offline design, not a live agent.** This pass delivers:

- A documented, portable `RuntimeObservation` schema
  (`Asgard/Heimdall/Security/runtime/models.py`).
- An offline ingestion loader for JSON/JSONL batches of observations
  (`Asgard/Heimdall/Security/runtime/ingest.py::load_observations[_from_file]`).
- A merge function that folds observations into a static `TaintReport`
  (`ingest.py::merge_runtime_observations`).
- This design doc, describing how a real per-language runtime agent would
  emit into this interface, and the roadmap to build one.

Nothing in this module performs live instrumentation, spawns a process, or
makes a network call. It is pure, deterministic, stdlib+pydantic offline
replay — consistent with `ASGARD_UPLIFT_GOAL.md`'s "no default network" and
"honest labeling" constraints.

## Why runtime observation at all (the Class B ceiling)

Static taint analysis (`Heimdall/Security/TaintAnalysis/`) is fundamentally
limited by undecidability: reflection, dynamic dispatch, `eval`, dynamically
computed `require`/`import` targets, and runtime configuration cannot be
resolved by inspecting source alone. WS5 (dynamic-construct surfacing)
converts *silent* misses on these constructs into an honest
`needs-review`/`DYNAMIC_CONSTRUCT` finding — but it still cannot prove
whether tainted data actually reaches the sink at runtime.

A runtime/IAST (Interactive Application Security Testing) agent closes that
gap by *observing* the program while it runs: it watches values flow from a
real source (an HTTP request, an env var, a file read) to a real sink (a SQL
call, a shell exec) during an actual execution — integration test, staging
traffic replay, or fuzz run. That is strictly stronger evidence than static
inference, because it is a witnessed event, not a graph-reachability guess.

It is also strictly *narrower*: a runtime agent only sees the paths that
were actually exercised during the observed run. It can prove a flow is
reachable; it can never prove a flow is *unreachable* (test coverage is
never exhaustive). This is the epistemic asymmetry the merge semantics below
are built around.

## The `RuntimeObservation` schema

Defined in `Asgard/Heimdall/Security/runtime/models.py`. Key design points:

- **Typed like a `TaintFlow`.** `source_type`/`sink_type` reuse
  `TaintSourceType`/`TaintSinkType` from
  `TaintAnalysis/models/taint_models.py` so a runtime observation can be
  matched against a static finding without a lossy translation layer.
- **Fingerprint, never raw value.** `tainted_value_fingerprint` is a
  non-reversible hash of the observed tainted value. The schema is designed
  so a runtime agent (which may see live user data, secrets, PII) never has
  to serialize sensitive payloads into a report artifact.
- **`trace_id` + `stack_frames`.** Correlates the observation to a single
  execution and gives a human a call path to inspect, without requiring a
  full stack-trace object model.
- **`timestamp_in` is always supplied by the caller.** This library never
  calls `time.time()`/`datetime.now()` internally — every observation
  carries its own timestamp, which keeps ingestion deterministic and makes
  golden-file/replay tests reproducible byte-for-byte.
- **`confidence_marker`** (`RuntimeConfidence`): `confirmed_at_runtime` (the
  agent directly traced tainted data reaching the sink) vs `suspected` (a
  lower-fidelity signal — e.g. a heuristic hook that saw a plausible but not
  fully-traced flow). Only `confirmed_at_runtime` observations can mark a
  static finding as confirmed; `suspected` observations still merge in as
  new findings, but at a lower confidence bucket (`possible`, not
  `certain`) — see `_observation_to_runtime_flow` in `ingest.py`.

`RuntimeObservationBatch` is the serializable envelope
(`{"schema_version", "generated_by", "observations": [...]}`) a runtime
agent would write to disk; the loader also accepts a bare JSON array or
JSONL (one observation per line) for lower-ceremony producers.

## Merge semantics

`merge_runtime_observations(static_report, observations) -> TaintReport`
(new report returned; input `TaintReport` is never mutated):

1. **Match static findings against observations.** Matching key:
   `(sink_location.file_path, sink_location.line_number, sink_type)`, with a
   tolerant fallback to `(file_path, sink_type, cwe_id)` when the exact line
   diverges — e.g. static analysis reports the call-expression line while a
   runtime agent reports the resolved-frame line of a wrapped/decorated
   call. A matched static `TaintFlow` is marked `confirmed_at_runtime=True`
   and its `runtime_trace_ids` gains the observation's `trace_id`. This
   *raises* the finding's epistemic status — runtime proof is strictly
   stronger than a static guess — but it never touches `severity`
   (blast-radius is a property of the sink, not of how it was detected).
2. **Runtime-only observations become new findings.** An observation with no
   matching static flow — the case that matters most, since it is exactly
   the class of dynamic-dispatch/reflection flow static analysis is blind to
   — is added as a brand-new `TaintFlow` with `origin="runtime"`. These are
   built from the observation directly (source/sink location, stack frames
   as intermediate steps, CWE if known) and default to `severity="high"`
   with `confidence_bucket` driven by the observation's `confidence_marker`
   (`certain` for `confirmed_at_runtime`, `possible` for `suspected`) — they
   were *witnessed*, so they don't sit in the same "algorithmic guess"
   bucket as an unconfirmed static finding.
3. **Absence is never evidence of safety.** A static finding with no
   matching observation is carried through **completely unchanged** — same
   confidence, same severity, same bucket. `merge_runtime_observations`
   contains no code path that lowers a static finding's confidence,
   severity, or bucket based on the *lack* of a runtime observation. This is
   the WS7 "never downgrade" invariant from the plan, and it is enforced by
   `test_absence_of_observation_never_downgrades_static_finding` in
   `Asgard_Test/tests_Heimdall/L0_Mocked/Runtime/test_runtime_observation_merge.py`.

### Epistemic framing at a glance

| State | Meaning | Confidence direction |
|---|---|---|
| Static-only, unconfirmed | Static taint analysis inferred a flow; no runtime signal either way | Unchanged (`possible`/`probable` per static engine) |
| Static + runtime-confirmed | Static inferred it, and a runtime agent actually witnessed it | Raised to `certain`, `confirmed_at_runtime=True` |
| Runtime-only (`origin="runtime"`) | A runtime agent witnessed a flow static analysis never modeled (reflection, dynamic dispatch, computed `import`) | `certain`/`possible` depending on `confidence_marker`, always `origin="runtime"` so it's traceable to its source |
| Static-only, no observation this run | Static inferred it; this particular observed execution didn't happen to exercise it | **Unchanged** — never downgraded. Non-observation ≠ non-existence. |

## How a real per-language runtime agent would emit into this interface

None of the agents below are implemented in this pass; this is the roadmap
the interface is designed to support without a schema break.

- **Node.js — `async_hooks` + a shim on well-known sink modules.** Hook
  `async_hooks.createHook` to track async-context propagation of a tainted
  marker (e.g. a `WeakSet`/branded wrapper set on values originating from
  `req.query`/`req.body`/`req.headers`), and monkey-patch (or use
  `--require`-injected wrappers around) sink modules (`mysql2`, `pg`,
  `child_process`, `vm`) to check the marker at the call site and emit a
  `RuntimeObservation` (fingerprint via a fast non-cryptographic hash of the
  value, `trace_id` from the async-hook execution context, `stack_frames`
  from `Error().stack` at the hook site).
- **Python — `sys.settrace`/`sys.monitoring` (3.12+) or import hooks.** A
  lower-overhead alternative to full `settrace`: wrap known source call
  sites (`flask.request.args.get`, `os.environ.get`) via import hooks that
  patch the returned value with a taint-tracking subclass (`str` subclass
  carrying a source tag), and wrap known sinks (`cursor.execute`,
  `subprocess.run`, `eval`) to check the tag. `sys.settrace`/`sys.monitoring`
  would be reserved for a deeper, opt-in trace mode when the lightweight
  wrapper approach can't reach a sink (e.g. taint lost through a C
  extension boundary).
- **Java — a `java.lang.instrument` agent.** Standard IAST approach:
  bytecode-instrument known source APIs (`HttpServletRequest.getParameter`)
  and sink APIs (`Statement.execute`, `Runtime.exec`, `ObjectInputStream.readObject`)
  via ASM/Byte Buddy, propagate a taint tag through a `ThreadLocal`-scoped
  context, and emit a `RuntimeObservation` on sink invocation with tag
  present. This is the same architecture as Contrast/Checkmarx IAST agents.
- **Go — build-tag-gated wrapper injection.** Go has no runtime hook
  ecosystem comparable to the above; the practical approach is a `go vet`-style
  AST rewrite pass (or `//go:build iast` conditional compilation) that
  wraps calls to `database/sql`, `os/exec`, and HTTP handler parameter
  accessors with taint-tracking shims at build time for an `-tags iast`
  instrumented test/staging binary — never the default build.

**Common contract for all agents:** they only ever *write* `RuntimeObservation`
records (JSON/JSONL, matching `RuntimeObservationBatch`) to a file or
stream; they never call into Asgard directly, and Asgard never loads a
network endpoint by default to fetch them (opt-in only, mirroring the WS6
LLM-triage layer's `--assist` posture). The offline loader in this module is
the only consumer.

## Roadmap to a live agent

1. **This pass (delivered):** schema + offline loader + merge + design.
2. **Next:** a reference *lightweight* Python import-hook agent (source
   wrapping only, no `sys.settrace` overhead) as the first real producer,
   validated by replaying its output through this same
   `merge_runtime_observations` path — proves the interface against a real
   (not synthetic) observation stream.
3. **Then:** wire `merge_runtime_observations` into the Heimdall CLI as an
   opt-in `--runtime-observations <path>` flag on the taint/scan commands
   (default OFF, matching the "opt-in complementary layer" framing in
   `_Docs/Planning/TaintGaps/00_Plan.md`), and add the merged
   `confirmed_at_runtime`/`origin` fields to the SARIF/JSON report
   emitters.
4. **Later:** Node async-hooks and Java bytecode agents, each validated the
   same way — real agent, replayed through the unchanged merge interface.
   No schema change should be required; if one language's agent needs a
   field the schema doesn't have, that is a signal the schema itself needs
   to grow (additively, with defaults) before the agent ships.

## Non-goals of this pass

- No live process instrumentation, no bytecode weaving, no `sys.settrace`
  wiring — those belong to the per-language agents in the roadmap above.
- No network transport for observations (e.g. no agent-to-server streaming
  API) — offline file replay only, honoring the "no default network"
  invariant.
- No automatic re-scoring of severity from runtime data — severity stays a
  property of the sink's worst-case impact, not of how a finding was
  detected (severity ⊥ confidence, per `ASGARD_UPLIFT_GOAL.md`).
