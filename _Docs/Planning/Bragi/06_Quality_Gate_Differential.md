# Plan 06 — Quality Gate: Differential ("Clean As You Code") Evaluation and Two-Tier CI

**Priority: P1** — the gate is where Bragi meets CI; today it can only judge whole-project absolutes, which at any real scale means it either never fails or always fails.
**Research basis:** `_Docs/Research/Bragi/Completed/RESEARCH_15` (delta aggregation, PR-scoped caches, skip-unchanged, SonarQube PR pipeline), `DEEPTHINK_09` (waterline ratchet, tiered content-addressable caching, hotspot priority = severity × churn × reachability, root-cause grouping), `DEEPTHINK_06` (two-tier CI: <30 s blocking intra-file tier; unbounded async project-wide tier), `DEEPTHINK_02` (blocking gates demand ~99% precision — deterministic rules only).

---

## 1. Rationale (what the research says)

- DEEPTHINK_09 §4: at scale there are always thousands of legacy violations; a gate must be **strictly differential** — "the build only fails if the developer introduces *new* technical debt", filtering 50,000 global violations to 0–3 actionable PR comments.
- DEEPTHINK_02: a blocking CI gate operates at ~99% precision or developers route around it; only zero-ambiguity, mechanically verifiable conditions belong there. Subjective heuristics gate nothing, ever.
- DEEPTHINK_06: bifurcate — Tier 1 blocking (<30 s budget, intra-file scope: syntax, complexity bounds, deterministic bugs, presence checks) vs Tier 2 asynchronous (project-wide: cycles, coupling, clone sweep, composite score trends) that feeds dashboards/tickets and gates *releases*, not commits.
- RESEARCH_15: the machinery is delta aggregation (new − resolved, applied arithmetically to a persisted aggregate — Plan 02 Phase E builds exactly this), interface-hash invalidation (Plan 03 §3.1), and SonarQube's discipline that **PR-scoped caches are discarded, only main-branch baselines persist** (prevents cache pollution across parallel PRs).
- DEEPTHINK_09's dashboard prioritization for the async tier: `Priority = severity_weight × churn_multiplier × reachability` — churn comes from Plan 02's `_git_friction.py`, reachability from Plan 03's centrality.

## 2. Current state (gap)

`Asgard/Bragi/QualityGate/` (models 150 lines, services 440 lines):

- Absolute project-level conditions only (`TECHNICAL_DEBT_HOURS < X`, `SECURITY_RATING == A`). No notion of new-code period, changed lines, or baseline — a legacy codebase can never adopt the gate without turning everything off.
- **Missing metric silently passes**: `evaluate()` marks a condition `passed=True` with "condition skipped" when the metric isn't supplied. A gate whose security scan failed to run reports PASSED — the same epistemic bug Plan 01 §3.5 fixes in ratings, unfixed here.
- `QualityGateConfig.small_change_threshold_lines` exists (a differential concept!) but nothing computes changed lines — dead config.
- No `COMPOSITE_SCORE`/risk-profile metrics (Plan 01 Phase D expects a `COMPOSITE_SCORE` MetricType); no distinction between gate-eligible deterministic metrics and advisory ones; no tier concept; `extract_metrics_from_reports` is another duck-typed `getattr` walk (consolidate with Plan 01's `_report_extractors.py`).

## 3. Target state

### 3.1 Honest condition semantics (fixes first)

- Missing metric → `ConditionResult.passed=None`, status contribution `NOT_EVALUATED`; gate summary lists unevaluated conditions explicitly. New `on_missing: fail | warn | skip` per condition (default `warn`), so "security scan must have run" is expressible. Mirrors Plan 01's `ScoreConfidence`; a skipped scan can no longer produce a green gate silently.
- Metric registry annotates each `MetricType` with `determinism: FACT | HEURISTIC` (shared vocabulary with Plan 04). Config validation warns when `error_on_fail=True` is attached to a HEURISTIC metric (DEEPTHINK_02's 99%-precision rule), and the default gates never do it.

### 3.2 Differential gate (`evaluate_differential`, new)

```python
class NewCodeDefinition(BaseModel):
    mode: Literal["reference_branch", "since_commit", "days"]
    value: str

class DifferentialInput(BaseModel):
    changed_files: Dict[path, List[LineRange]]   # from git diff base...head
    base_state: ProjectState                      # persisted main-branch aggregate
    head_reports: ...                             # scan of changed files only
```

- Violation matching by the AST-stable fingerprint from Plan 04 (`hash(rule_id, module, symbol, normalized_snippet)`) — a violation is NEW iff its fingerprint is absent from `base_state` (line-shift immune, per DEEPTHINK_11/09).
- New-code condition set evaluated over new/changed code only: `new_blocker_issues == 0`, `new_code_composite_score >= 0.80 (B)`, `debt_delta_minutes <= 0` ("waterline ratchet": the aggregate may only improve, DEEPTHINK_09), `new_prohibited_licenses == 0` (Plan 03).
- Debt delta and per-file rescoring come from Plan 02 Phase E's `_debt_state_store` (`analyze_delta(changed_files)`) — this plan is its named consumer.
- Legacy violations in files the PR touched on *modified lines* are surfaced as warnings (the DEEPTHINK_09 "or legacy violations that the developer directly modified" rule); untouched legacy is invisible in this channel.
- `small_change_threshold_lines` finally wired: below it, gate returns `PASSED (small change)` with conditions annotated as skipped-by-policy.

### 3.3 Two-tier gate definitions

Ship two built-in gates replacing the single "Asgard Way":

| Gate | Trigger | Budget | Conditions |
|---|---|---|---|
| `asgard-pr` (Tier 1, blocking) | PR / pre-commit | <30 s | new-code conditions of §3.2, FACT-class metrics only, changed-files scan via incremental cache |
| `asgard-main` (Tier 2, non-blocking / release gate) | merge to main / nightly | unbounded | absolute conditions (current gate behavior), `COMPOSITE_SCORE`, `RISK_PROFILE_E_LOC_PCT == 0`, cycle count, license compliance, hotspot report |

- Tier 2 output includes DEEPTHINK_09's prioritized hotspot list (`severity × churn × reachability` using Plan 02 friction + Plan 03 centrality) and root-cause grouping ("fixing signature of `core.auth.validate` resolves 412 downstream findings" — group findings by shared origin symbol before rendering).
- Main-branch scan persists `ProjectState` (`.asgard_cache/bragi_project_state.json`: violation fingerprints, per-file scores, debt aggregate, dep-graph interface hashes). PR evaluations load it read-only and never write back (RESEARCH_15's SonarQube cache discipline).

### 3.4 New metric types

Extend `MetricType`: `COMPOSITE_SCORE`, `RISK_PROFILE_E_LOC_PCT`, `NEW_BLOCKER_ISSUES`, `NEW_CODE_COMPOSITE_SCORE`, `DEBT_DELTA_MINUTES`, `PROHIBITED_LICENSE_COUNT`, `DEPENDENCY_CYCLES`, `SCAN_COMPLETENESS` (fraction of expected report inputs present — gate on your own confidence).

## 4. Concrete file/module changes

| File | Change |
|---|---|
| `QualityGate/models/quality_gate_models.py` | `NewCodeDefinition`, `DifferentialInput`, `ProjectState`, `on_missing`, `determinism` annotation, new MetricTypes, tri-state `ConditionResult.passed`. |
| `QualityGate/services/quality_gate_evaluator.py` | NOT_EVALUATED semantics; `evaluate_differential()`; small-change wiring. |
| `QualityGate/services/_differential_engine.py` (new) | git diff parsing (`git diff --unified=0 base...head`), fingerprint matching against `ProjectState`, new/legacy-touched partition. |
| `QualityGate/services/_project_state_store.py` (new) | Load/save/merge `ProjectState`; write-only-on-main policy flag. |
| `QualityGate/services/_hotspot_ranker.py` (new) | severity × churn × reachability priority; origin-symbol root-cause grouping. |
| `QualityGate/services/_quality_gate_helpers.py` | Replace `extract_metrics_from_reports` getattr-walk with Plan 01's typed `_report_extractors`; add `asgard-pr` / `asgard-main` builders (keep `build_asgard_way_gate` as alias to `asgard-main`). |
| `Heimdall/cli/handlers/` gate handler | `--diff base...head`, `--new-code-since`, `--tier` flags; exit code contract: fail only on Tier-1 error conditions. |

## 5. Phased implementation

1. **Phase A — honesty fixes**: NOT_EVALUATED semantics, `on_missing`, determinism annotations, `SCAN_COMPLETENESS`. Small and independent; corrects a real false-green today.
2. **Phase B — project state + fingerprints**: state store, fingerprint matching (depends on Plan 04 Phase D fingerprint function; can ship with a line-tolerant interim hash if 04 lags).
3. **Phase C — differential gate**: diff engine, new-code conditions, `asgard-pr` gate, small-change wiring; consumes Plan 02 Phase E delta store.
4. **Phase D — Tier 2**: `asgard-main` gate with composite/risk-profile metrics (needs Plan 01 Phase B), hotspot ranker, root-cause grouping.

## 6. Testing considerations

- Honesty: gate with a security condition and no security report → status includes NOT_EVALUATED, never PASSED (the named regression for today's bug); `on_missing=fail` → FAILED.
- Differential correctness property: for a synthetic repo pair (base, head), `new_violations == scan(head) − scan(base)` matched by fingerprint — verified against a from-scratch double scan (consistency oracle, same pattern as Plan 02's delta-store test).
- Line-shift immunity: PR that only inserts 10 lines above a legacy violation → 0 new violations.
- Waterline: PR fixing 2 issues and adding 1 smaller one → `debt_delta_minutes < 0` passes ratchet; inverse fails.
- Cache discipline: PR evaluation never mutates `ProjectState` on disk (filesystem spy); main-branch run does.
- Tier-1 budget: `asgard-pr` on a 50-file change over the fixture monorepo completes within the CI budget with warm cache (marked perf test, generous bound).
- Backward compat: `build_asgard_way_gate()` still importable and equivalent to `asgard-main`; existing gate tests pass with tri-state semantics behind the legacy `evaluate()` path (missing → warn by default preserves pass/fail for currently-passing suites — verify against `Asgard_Test/tests_Bragi/L0_Mocked/QualityGate/`).
