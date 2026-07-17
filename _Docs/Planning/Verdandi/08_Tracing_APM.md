# 08 — Tracing & APM: Sweep-Line Critical Path, Causal Normalization, Service-Map Hardening

## Research-Backed Rationale

- **DEEPTHINK_06**: a trace is "a lossy chronological record of uncoordinated schedulers", not a clean DAG. Naive longest-path fails on: (1) fire-and-forget async children (5 s background task hijacks a 50 ms request's path), (2) parallel fan-out jitter (gap-threshold heuristics break under load), (3) clock skew (negative edges, causality violations), (4) missing spans (dark matter). Prescribed algorithm: **causal normalization (orphan adoption → symmetric-RTT clock shift → async truncation) + time-slicing + recursive sweep-line with latest-finisher dominance + self-time rollup**, with explicit confidence flags (`HEAVY_CLOCK_SKEW_ADJUSTED`, `ORPHANED_SUBTREE_RECOVERED`, `HIGH_UNATTRIBUTED_TIME` > 30%, `SEVERE_ASYNC_TRUNCATION`).
- **DEEPTHINK_10**: service maps require identity normalization (infra-anchored composite keys; safe lexical canonicalization; *never* auto-strip `-api`/`-worker` suffixes or versions), virtual messaging nodes from PRODUCER/CONSUMER span kinds (`svc → [kafka: topic] → svc`, dashed async edges), dimensional edges with semantic zoom, ghost-edge decay, threshold pruning (< 0.1% traffic hidden **unless error rate > 0**), and ego-centric N-hop views.
- **DEEPTHINK_11**: dependency-graph centrality feeds the portfolio SRI weighting (Plan 02 §8).

## Current State

- `Tracing/services/critical_path_analyzer.py`: longest-path via `find_critical_path` + self-time subtraction. None of the four edge cases handled; no confidence flags.
- `Tracing/services/trace_parser.py` / `_span_parsers.py`: OTLP-ish parsing (assumed; spans carry `start_time_unix_nano`).
- `APM/services/service_map_builder.py`: builds nodes/edges from spans, cycle detection, up/downstream, depth. No identity normalization, no messaging virtual nodes, no pruning/ghost edges, no centrality export.

## Target State

### A. Causal normalization pipeline (`Tracing/services/causal_normalizer.py`, new)
Ordered passes over a parsed trace, each emitting flags:
1. **Orphan adoption**: spans with missing/unknown `parent_span_id` re-parented to the tightest ancestor whose `[start, end]` fully bounds them; fallback to root. Flag `ORPHANED_SUBTREE_RECOVERED`.
2. **Clock-skew correction** (per cross-host client/server RPC pair):
   `transit = ((client_end - client_start) - (server_end - server_start)) / 2`
   `offset = (client_start + transit) - server_start`; shift server span **and all its descendants** by `offset` (preserves local ordering). Flags: `HEAVY_CLOCK_SKEW_ADJUSTED` when `|offset| > 50 ms` or computed transit < 0.
3. **Async truncation** (top-down): `span.effective_end = min(span.end, parent.effective_end)`. Flag `SEVERE_ASYNC_TRUNCATION` when truncated duration > 25% of the child's raw duration.

### B. Sweep-line critical path (`Tracing/services/critical_path_analyzer.py` rewrite of core)
1. Collect all unique `start` / `effective_end` timestamps → sorted slice boundaries.
2. For each slice, recurse from root: 0 active children → credit slice to current span's **self-time**; 1 active child → recurse; > 1 → recurse only into the child with **max effective_end** (latest-finisher dominance — no gap thresholds).
3. Aggregate credited time per span; spans with credit > 0 form the critical path; `contribution_ms` = credited time (replaces the current subtraction heuristic).
4. Flags: `HIGH_UNATTRIBUTED_TIME` when > 30% of the path is intermediate-span self-time ("add instrumentation to service X").
Complexity O(S·D) per slice worst case; fine for single-trace batch analysis. Keep the old algorithm behind `strategy="legacy"` for one release.
Documented assumptions (surface in result model): symmetric network latency; wait-state assumption (active child ⇒ blocked parent); early-finishing async is indistinguishable from sync.

### C. Service map hardening (`APM/services/service_map_builder.py` + helpers)
1. **Identity resolution** (`APM/services/_identity_resolver.py`, new): composite key `env:namespace:canonical_name` when resource attrs (`k8s.namespace.name`, `deployment`) exist; else lexical canonicalization only (lowercase, unify `_`/space/camelCase → `-`). Explicit non-goals coded as tests: no suffix stripping, no version merging. `AliasRegistry` (dict-in, dict-out) for operator-approved merges; `suggest_merges()` proposes candidates sharing identical upstream+downstream sets.
2. **Messaging virtual nodes**: spans with `span.kind == PRODUCER/CONSUMER` + `messaging.system`/`messaging.destination.name` create `[system:destination]` nodes and async (dashed) edges; parameterized rollup for generated names (`amq.gen-* `, UUID-like segments) to prevent cardinality explosion.
3. **Edge dynamics**: edges carry windowed counts + error counts; `prune(min_traffic_share=0.001, keep_if_errors=True)`; `ghost_edges(current_window, previous_window)` → present-before/absent-now edges marked `ghost=True`.
4. **Ego view**: `ego_subgraph(service, upstream_hops=1, downstream_hops=2)`.
5. **Centrality export**: `centrality() -> dict[service, float]` (degree-weighted or simple PageRank power iteration, 20 iters) consumed by `SLO/portfolio_scorer` (Plan 02).

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Tracing/models/tracing_models.py` | `effective_end_ns`, `ConfidenceFlag` enum, `CriticalPathResult {flags, assumptions, strategy}`. |
| `Tracing/services/causal_normalizer.py` (new) | §A passes. |
| `Tracing/services/critical_path_analyzer.py` | Sweep-line core; legacy strategy retained. |
| `Tracing/services/_path_helpers.py` | Slice generation, latest-finisher selection. |
| `APM/services/_identity_resolver.py` (new) | Canonicalization + alias registry + merge suggestions. |
| `APM/services/service_map_builder.py` | Virtual nodes, pruning, ghost edges, ego view, centrality. |
| `APM/models/apm_models.py` | `ServiceIdentity`, `EdgeStats {calls, errors, async, ghost}`, `VirtualNode`. |
| `cli/` | `verdandi tracing critical-path --strategy sweepline`, `verdandi apm map --ego <svc> --prune`. |

## Phased Steps

1. Causal normalizer (pure functions; testable per pass).
2. Sweep-line path + flags (feature-flagged, default after parity run).
3. Identity resolver + alias registry.
4. Virtual messaging nodes + pruning/ghost/ego.
5. Centrality export → unblock Plan 02 portfolio weighting.

## Testing Notes

- L0 skew: client 0–100 ms calling server reporting start=-20 ms (skewed) → offset ≈ +25 ms, descendants shifted, no negative edges; server slower than client span → transit < 0 → flag.
- L0 truncation: parent 0–50 ms, async child 10–5000 ms → child effective_end=50 ms; path ≤ 50 ms; `SEVERE_ASYNC_TRUNCATION` set.
- L0 sweep-line parallel: three children 0–30/0–40/5–45 under parent 0–50 → credits: child3 gets [5,45] minus overlaps per latest-finisher; gaps credited to parent self-time; total credited == parent duration exactly (conservation invariant — assert in tests).
- L0 dark matter: parent 500 ms, children sum 100 ms → 400 ms parent self-time; > 30% → `HIGH_UNATTRIBUTED_TIME`.
- L0 identity: `Payment_Service` == `paymentService` → `payment-service`; `payment-api` vs `payment-worker` NOT merged.
- L0 map: producer/consumer spans yield `A → [kafka:orders] → B` with async edges; 0.05%-traffic edge hidden, same edge with 1 error visible.
