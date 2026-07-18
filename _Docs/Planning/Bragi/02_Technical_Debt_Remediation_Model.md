# Plan 02 — Technical Debt & Remediation Model (SQALE-proper, ROI-driven, Uncertainty-aware)

**Priority: P0** — the debt number is the single input the Maintainability rating hangs on; today it is a linear sum of guessed hours.
**Research basis:** `_Docs/Research/Bragi/Completed/RESEARCH_04` (SQALE / CISQ decomposition), `DEEPTHINK_05` (effort estimation & aggregation), `DEEPTHINK_07` (severity calibration, churn/age modulation), `DEEPTHINK_14` (uncertainty communication), `RESEARCH_15` (incremental delta aggregation), `RESEARCH_01` (TDR anchors).

---

## 1. Rationale (what the research says)

RESEARCH_04 lays out the canonical SQALE machinery Bragi should implement properly:

- **Remediation function types**: *constant* per issue (naming fix), *linear* (coefficient × complexity points above threshold), *linear with offset* (offset = context-switch cost of opening the file). SQUORE severity constants: Tiny 1 min, Low 10 min, Medium 30 min, High 1 h, Huge 8 h.
- **Non-remediation function (SBII)**: business-impact penalty factors Blocking 1000, High 100, Medium 15, Low 10, Info 4. The ratio non-remediation/remediation is the refactoring-ROI ranking key.
- **TDR** = remediation cost / (0.06 days × LOC) with the A–E 5/10/20/50 grid (already in Bragi).
- **Empirical correction**: Lenarduzzi/Taibi 2020 — actual fix time exceeded SonarQube estimates in only **3%** of cases; estimates are overwhelmingly pessimistic. RESEARCH_04's blueprint: reduce trivial-smell constants to **1–2 min** (vs 5–10).
- **Architectural debt**: linear addition of local violations systematically underestimates architectural debt (cycles, layer erosion). CISQ fix: multiply base effort by an **Exposure Factor** derived from graph centrality of the flawed component.

DEEPTHINK_05 adds the aggregation law that kills naive `count × unit_cost`:

```
Total_Effort = Cost_Context + Σ_{i=1..n} (Cost_Marginal × d^(i-1))
```

- `Cost_Context` ≈ fixed setup cost per file/batch (checkout, mental model, PR ceremony; ~30 min).
- `d` = batchability discount: near 0 for *mechanical* debt (50 missing docstrings = ~35 min, not 4 h), high for *cognitive* debt (multiple God classes need independent thought).
- **Rewrite cap**: if aggregated remediation approaches rewrite-from-scratch time, cap the debt and pivot the recommendation to "rewrite".
- **Prioritization = ROI**: `Priority = Expected Friction (interest, from churn/authors/defect-density) / Remediation Effort (principal)`. Debt in dormant code has interest ≈ 0 (Lindy effect, DEEPTHINK_07 "Sleeping Bear").
- **Uncertainty**: never point estimates — output confidence intervals ("1–3 days") with the reason for width ("high complexity + 12% branch coverage").

RESEARCH_15 gives the incremental recipe: compute per-PR debt **delta** (new issues − resolved issues) and apply arithmetically to a persisted aggregate — never rescan the world.

## 2. Current state (gap)

- `Asgard/Bragi/Quality/models/debt_models.py`: `DebtItem.effort_hours` is a single point estimate; `DebtReport.add_item` does `total_debt_hours += item.effort_hours` — pure linear addition, exactly the anti-pattern DEEPTHINK_05 §2 describes.
- `DebtItem` ROI exists (`roi = business_impact × interest_rate / effort`) but `interest_rate` and `business_impact` have no data source — no churn, no author fragmentation, no defect linkage.
- `Asgard/Bragi/Quality/services/technical_debt_analyzer.py`: `debt_ratio = total_debt_hours / LOC × 1000` — non-standard denominator, inconsistent with the Ratings calculator which independently invents `estimated_dev_hours = LOC/100` (i.e., 0.6 min/LOC — **50× off** the industry 30 min/LOC anchor from RESEARCH_01/04; the resulting percentages only accidentally resemble SonarQube's).
- `_debt_workers.py`: per-category effort constants exist (`config.effort_models.*`) but there is one number per debt type, no function *shape* (constant/linear/offset), no severity-linked minutes, no batching.
- No non-remediation/impact score, no exposure multiplier, no confidence interval, no churn modulation, no rewrite cap, no incremental delta.

## 3. Target state

### 3.1 Remediation cost model (`RemediationModel`)

Each debt rule declares a remediation function, not a scalar:

```python
class RemediationFunction(BaseModel):
    kind: Literal["constant", "linear", "linear_with_offset"]
    base_minutes: float          # constant part / offset
    coefficient_minutes: float   # per unit above threshold (linear kinds)
    unit: str                    # "complexity_point", "duplicated_block", ...
    batchability: float          # d ∈ [0,1]; 0.05 mechanical, 0.8 cognitive
```

Default constants (RESEARCH_04 + pessimism correction):

| Severity class | Minutes | Notes |
|---|---|---|
| Tiny (naming, unused import, missing docstring) | **1–2** | corrected down from SQUORE's 10 per Lenarduzzi finding |
| Low | 10 | |
| Medium | 30 | |
| High | 60 | |
| Huge (architectural, cycle break) | 480 | plus Exposure multiplier |

### 3.2 Aggregation (`DebtAggregator`)

Group items by `(file, rule)`; within a group apply the geometric-discount sum with the rule's `batchability`; add one `Cost_Context` (default 30 min) per *file* batch, not per item. Then:

- **Exposure multiplier** for design/architectural items: `1 + β·centrality`, centrality = afferent-coupling percentile of the module from `Bragi/Dependencies` (`DependencyReport.modules[].afferent_coupling`) — the CISQ Exposure Factor. Leaf modules ×1.0; a module imported by 80% of the codebase gets the max multiplier (default ×3).
- **Rewrite cap** per file: `rewrite_minutes ≈ LOC × 0.5 min` (the 30 min/LOC dev-cost anchor is for *green-field* cost; use a configurable fraction). If `Σ remediation > rewrite_minutes`, cap and set `recommendation = REWRITE`.

### 3.3 Interest & ROI (`InterestModel`)

New optional VCS telemetry source (git only, subprocess `git log --numstat --since=12.months`):

```python
class FileFriction(BaseModel):
    churn_commits_90d: int
    distinct_authors_12m: int
    bugfix_commits_12m: int      # commits whose message matches fix/bug/hotfix patterns
```

`interest = w1·churn_norm + w2·author_fragmentation + w3·bugfix_density` (percentile-normalized within the repo).
`priority = interest × non_remediation_factor / remediation_minutes` — where `non_remediation_factor` uses the SBII constants (Blocking 1000 / High 100 / Medium 15 / Low 10 / Info 4).

Churn/age modulation of severity (DEEPTHINK_07): items in files untouched ≥ 24 months are downgraded one action tier ("Sleeping Bear") and tagged `fix_when_touching`; high-metric + high-churn files retain maximum severity ("Minefield").

### 3.4 Uncertainty (`EffortInterval`)

```python
class EffortInterval(BaseModel):
    low_minutes: float
    high_minutes: float
    confidence: Literal["high", "medium", "low"]
    width_reason: str   # e.g. "high cognitive complexity + no test coverage data"
```

Width drivers: file test coverage (if a Coverage report is supplied → narrow), max cognitive complexity (high → widen ×2), language tooling (static typing presence → narrow). Reports must render ranges, never single numbers (DEEPTHINK_05/14).

### 3.5 Incremental delta aggregation (RESEARCH_15)

Persist `debt_state.json` (per scan root, content-hash keyed per file): on re-scan, only files whose SHA-256 changed are re-analyzed; project totals updated arithmetically (`total += Σ new_file_debt − Σ old_file_debt`). This is a prerequisite for PR-differential gating (Plan 06).

## 4. Concrete file/module changes

| File | Change |
|---|---|
| `Asgard/Bragi/Quality/models/debt_models.py` | Add `RemediationFunction`, `EffortInterval`, `FileFriction`, `DebtRecommendation` enum (`FIX`, `FIX_WHEN_TOUCHING`, `REWRITE`, `TOLERATE`). `DebtItem` gains `effort_interval`, `non_remediation_factor`, `priority_score`; keep `effort_hours` as the interval midpoint for backward compat. |
| `Asgard/Bragi/Quality/services/_remediation_model.py` (new) | Rule-id → `RemediationFunction` registry with the constants table above; config-overridable via `DebtConfig.effort_models`. |
| `Asgard/Bragi/Quality/services/_debt_aggregator.py` (new) | Batching sum, context cost, exposure multiplier, rewrite cap. Consumes an optional `DependencyReport` for centrality. |
| `Asgard/Bragi/Quality/services/_git_friction.py` (new) | `collect_friction(repo_root) -> Dict[path, FileFriction]`; degrade gracefully (all-None) outside a git repo or when git missing. |
| `Asgard/Bragi/Quality/services/technical_debt_analyzer.py` | Wire aggregator + friction; fix `debt_ratio` to the standard TDR: `total_debt_minutes / (LOC × 30 min)` × 100. Emit top-N `priority_score` items as "High-Yield Refactors" (DEEPTHINK_05 §3 dashboard). |
| `Asgard/Bragi/Ratings/services/ratings_calculator.py` | Delete the local `estimated_dev_hours = LOC/100` invention; consume `debt_report.debt_ratio` computed by the analyzer (single source of truth for TDR). |
| `Asgard/Bragi/Quality/services/_debt_state_store.py` (new) | Content-hash keyed per-file debt cache + delta arithmetic (RESEARCH_15). Store under `.asgard_cache/bragi_debt_state.json`. |

## 5. Phased implementation

1. **Phase A — TDR unification**: standardize the ratio (30 min/LOC), fix the Ratings-side duplication. Small, high-value, corrects a 50× calibration bug.
2. **Phase B — remediation functions**: registry + severity minutes + pessimism-corrected constants; `EffortInterval` on `DebtItem`.
3. **Phase C — aggregation**: batching/context-cost/rewrite-cap; exposure multiplier fed by `DependencyReport`.
4. **Phase D — interest/ROI**: git friction collector, priority score, severity modulation, High-Yield Refactors output.
5. **Phase E — incremental state**: delta store; expose `analyze_delta(changed_files)` for Plan 06's PR gating.

## 6. Testing considerations

- Unit: 50 identical missing-docstring items in one file with `batchability=0.05` must total ≈ context(30) + Σ 2·0.05^(i−1) ≈ **~32 min**, not 100 min (DEEPTHINK_05 worked example).
- TDR golden test replicating RESEARCH_04's worked example: 63,987 LOC with 122,563 min debt → TDR 6.38% → grade B.
- Rewrite cap: synthetic 200-LOC file with 3000 min of debt → capped, `recommendation == REWRITE`.
- Friction collector: run against this repo's own git history in an L1 integration test; assert graceful degradation in a tmpdir without `.git`.
- Delta store: analyze fixture project, mutate one file, re-analyze; assert only that file re-processed (spy on worker) and totals equal a from-scratch scan (consistency property).
- Backward compat: `total_debt_hours` still populated (midpoints), existing `Asgard_Test/tests_Bragi` debt tests pass.
