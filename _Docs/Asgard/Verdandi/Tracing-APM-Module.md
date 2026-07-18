# Tracing & APM Modules

Covers `Asgard/Verdandi/Tracing/` (distributed trace parsing + critical path
analysis) and `Asgard/Verdandi/APM/` (span analysis, trace aggregation,
service dependency mapping). This doc reflects the Plan 08 uplift:
**causal trace normalization**, a **sweep-line latest-finisher critical
path** algorithm, and **service-map hardening** (identity resolution,
messaging virtual nodes, edge pruning/ghost edges, ego views, centrality).

A trace is a lossy chronological record of uncoordinated schedulers, not a
clean DAG: clock skew, orphaned spans, and fire-and-forget async children
all corrupt naive longest-path analysis. The passes below are ordered to
correct those artifacts before any path is computed.

## Tracing/services/causal_normalizer.py (new)

Three independently-testable pure functions, each `List[TraceSpan] ->
(List[TraceSpan], List[ConfidenceFlag])`, run in this order by
`normalize_trace(trace) -> (DistributedTrace, List[ConfidenceFlag], List[str])`:

1. **`adopt_orphans`** — spans with a missing/unknown `parent_span_id` are
   re-parented onto the tightest ancestor whose `[start, end]` window fully
   bounds them (the candidate with the latest start time among all
   bounding spans); falls back to the trace root when no bounding span
   exists. Flags `ConfidenceFlag.ORPHANED_SUBTREE_RECOVERED`.
2. **`correct_clock_skew`** — for each cross-host client/server RPC pair (a
   `SERVER`-kind span whose parent is a `CLIENT`-kind span in a different
   service):
   ```
   transit = ((client_end - client_start) - (server_end - server_start)) / 2
   offset  = (client_start + transit) - server_start
   ```
   The server span **and all its descendants** are shifted by `offset`
   (local ordering within the subtree is preserved). Flags
   `ConfidenceFlag.HEAVY_CLOCK_SKEW_ADJUSTED` when `|offset| > 50ms` or the
   computed transit is negative.
3. **`truncate_async`** — top-down pass setting
   `span.effective_end_ns = min(span.end_time_unix_nano, parent.effective_end_ns)`.
   Flags `ConfidenceFlag.SEVERE_ASYNC_TRUNCATION` when the truncated
   duration exceeds 25% of the child's raw duration.

`NORMALIZATION_ASSUMPTIONS` (3 fixed strings — symmetric network latency,
the wait-state assumption, early-finishing-async-indistinguishable-from-
sync) is always returned by `normalize_trace` alongside the flags.

## Tracing/models/tracing_models.py (additive)

- `TraceSpan.effective_end_ns: Optional[int]` — set by `truncate_async`;
  `TraceSpan.effective_end_time_unix_nano` property falls back to the raw
  end when unset.
- `ConfidenceFlag(str, Enum)` — `ORPHANED_SUBTREE_RECOVERED`,
  `HEAVY_CLOCK_SKEW_ADJUSTED`, `SEVERE_ASYNC_TRUNCATION`,
  `HIGH_UNATTRIBUTED_TIME`. These are epistemic annotations, **not alert
  severities** — anomalies are not alerts.
- `AnalysisOutcome(str, Enum)` — `OK` / `INSUFFICIENT_DATA`.
  `INSUFFICIENT_DATA` is a success outcome (no spans, no determinable root,
  or a zero/negative-duration root), never a failure.
- `CriticalPathResult` gained `strategy: str = "legacy"`,
  `flags: List[ConfidenceFlag] = []`, `assumptions: List[str] = []`,
  `outcome: AnalysisOutcome = OK` — all additive with backward-compatible
  defaults; existing consumers of `CriticalPathResult` are unaffected.

## Tracing/services/critical_path_analyzer.py

`CriticalPathAnalyzer.analyze(trace)` keeps its exact legacy signature and
behavior (naive longest-path + self-time subtraction), now additionally
accepting an optional `strategy: str = "legacy"` keyword — passing nothing
is 100% unchanged. `strategy="sweepline"` dispatches to the new algorithm.

### `analyze_sweepline(trace, apply_causal_normalization=True) -> CriticalPathResult`

1. Runs `causal_normalizer.normalize_trace(trace)` (unless
   `apply_causal_normalization=False`, e.g. the trace was already
   normalized upstream).
2. Collects every span's unique `start`/`effective_end` timestamp into
   sorted slice boundaries (`_path_helpers.build_slice_boundaries`).
3. For each slice `[t0, t1)`, recurses from the root
   (`_path_helpers.sweep_line_credit` / `_credit_slice`):
   - 0 active children (children whose window fully covers the slice) ->
     credit the slice to the current span's self-time.
   - 1 active child -> recurse into it.
   - >1 active children -> recurse only into the child with the maximum
     `effective_end` (**latest-finisher dominance** — no gap thresholds).
4. Aggregates credited nanoseconds per span; `CriticalPathSegment.contribution_ms`
   is that credited time (replaces the old self-time-by-subtraction
   heuristic for this strategy). **Conservation invariant**: the sum of all
   credited time equals the root span's effective duration exactly (see
   `test_three_overlapping_children_conservation_invariant`).
5. Flags `ConfidenceFlag.HIGH_UNATTRIBUTED_TIME` when self-time credited to
   intermediate (non-leaf) spans exceeds 30% of the root's effective
   duration.

Complexity is O(spans · depth) per slice — appropriate for single-trace
batch analysis, not high-QPS streaming.

## Tracing/services/_path_helpers.py (additive)

`effective_end_ns(span)`, `build_slice_boundaries(root, children)`,
`latest_finisher(active_children)`, `sweep_line_credit(root, children) ->
Dict[span_id, credited_ns]` — all pure functions, independently testable.
Existing `find_critical_path`, `calculate_parallelization_opportunity`,
`generate_path_recommendations`, `percentile` are unchanged.

## APM/services/_identity_resolver.py (new)

- `canonicalize_lexical(name) -> str` — lowercase, unify `_`/space/
  camelCase boundaries to `-`. **Never** strips suffixes (`payment-api` and
  `payment-worker` stay distinct) or version segments
  (`payment-service-v2` != `payment-service`) — these are explicit
  non-goals enforced by omission.
- `resolve_identity(raw_name, resource_attrs) -> ServiceIdentity` —
  composite key `env:namespace:canonical_name` when `k8s.namespace.name`
  (and optionally a deployment-environment attribute) is present in
  `resource_attrs`; otherwise `composite_key == canonical_name`.
- `AliasRegistry` — dict-in/dict-out operator-approved merge registry.
  `register(alias, canonical)`, `resolve(name)` (cycle-safe chain
  resolution), `to_dict()`, `from_dict(...)`,
  `suggest_merges(service_map) -> List[Tuple[str, str]]` (proposes, never
  applies, merges for services sharing an identical upstream+downstream
  neighbor set).

## APM/models/apm_models.py (additive)

- `ServiceIdentity` — `raw_name`, `canonical_name`, `composite_key`, `env`,
  `namespace`.
- `EdgeStats` — `calls`, `errors`, `is_async` (aliased `async`), `ghost`.
- `VirtualNode` — `key` (`"system:destination"`), `system`, `destination`,
  `node_type="messaging"`.
- `ServiceDependency` gained `is_async: bool`, `ghost: bool`,
  `traffic_share: float` (all default `False`/`0.0`).
- `ServiceMap` gained `virtual_nodes: List[VirtualNode]`,
  `identities: Dict[str, ServiceIdentity]`.

## APM/services/service_map_builder.py (additive methods)

- **`build_with_identity(spans, alias_registry=None) -> ServiceMap`** —
  identity-resolved variant of `build_from_spans`; populates
  `ServiceMap.identities`.
- **`build_messaging_view(spans) -> (List[VirtualNode], List[ServiceDependency])`**
  — spans with `kind` PRODUCER/CONSUMER and `messaging.system` /
  `messaging.destination.name` attributes produce `[system:destination]`
  virtual nodes and `is_async=True` edges
  (`service -> [system:destination]` for producers,
  `[system:destination] -> service` for consumers). Generated/UUID-like
  destination names (`amq.gen-*`, UUID segments) are parameterized to
  `<generated>` to prevent cardinality explosion.
- **`prune(service_map, min_traffic_share=0.001, keep_if_errors=True) -> ServiceMap`**
  — drops edges below `min_traffic_share` of total call volume, unless
  `keep_if_errors` and the edge has any errors (a 0.05%-traffic edge with 1
  error stays visible; the same edge with 0 errors is hidden). Sets
  `traffic_share` on kept edges.
- **`ghost_edges(current_window, previous_window) -> ServiceMap`** — edges
  present in `previous_window` but absent from `current_window` are
  appended with `ghost=True, call_count=0`.
- **`ego_subgraph(service_map, service, upstream_hops=1, downstream_hops=2) -> ServiceMap`**
  — restricts the map to `service` plus its N-hop upstream callers and
  M-hop downstream callees.

### `centrality()` — stable export for SLO/portfolio_scorer

```python
def centrality(
    self,
    service_map: ServiceMap,
    damping: float = 0.85,
    iterations: int = 20,
) -> Dict[str, float]:
```

Call-volume-weighted PageRank over the service dependency graph, pure
stdlib power iteration (20 default iterations, dangling nodes redistribute
mass uniformly each step). Returns `{service_name: score}`; scores sum to
~1.0 across all services in `service_map.services`; returns `{}` for an
empty map. **This exact name, signature, and return shape are a stable
contract** — `Verdandi/SLO/portfolio_scorer` consumes it by name for
portfolio SRI weighting (Plan 02 §8); do not rename or change the return
type without a coordinated migration.

## Regression tests

`Asgard_Test/tests_Verdandi/L0_Mocked/test_causal_normalizer_sweepline_servicemap.py`
(28 tests) encodes every worked example from
`_Docs/Planning/Verdandi/08_Tracing_APM.md` "Testing Notes": clock-skew
offset/negative-transit, async truncation ratio, orphan adoption
(tightest-ancestor + root fallback), the sweep-line parallel-children
conservation invariant, dark-matter unattributed-time flagging, identity
canonicalization (`Payment_Service`/`paymentService` -> `payment-service`;
`payment-api` vs `payment-worker` NOT merged), and the service-map
producer/consumer virtual-node + traffic-pruning/error-visibility scenario.
