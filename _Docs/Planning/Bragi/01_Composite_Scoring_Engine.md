# Plan 01 — Composite Scoring Engine (Hierarchical Gated Geometric Model)

**Priority: P0 (highest)** — this is the core of what Bragi Ratings is supposed to be.
**Research basis:** `_Docs/Research/Bragi/Completed/DEEPTHINK_01` (composite score design), `RESEARCH_01` (industry threshold calibration), `RESEARCH_04` (SQALE / SonarQube rating grids), `RESEARCH_05` (Maintainability Index critique), `DEEPTHINK_14` (uncertainty communication).

---

## 1. Rationale (what the research says)

DEEPTHINK_01 is explicit: a composite code quality score is a **Multi-Criteria Decision Analysis (MCDA)** problem. Naive aggregation produces a "Frankenstein metric" that double-counts collinear inputs (complexity ≈ LOC), unfairly penalizes large files, and lets trivial metrics mask critical vulnerabilities. The prescribed architecture is a **Hierarchical Gated Geometric Model**:

1. Map every raw metric to a utility `u ∈ [0,1]` with size-aware transforms (Laplace-smoothed densities, exponential decay).
2. Aggregate *within* categories with a **Weighted Arithmetic Mean** (metrics inside a category are substitutable).
3. Aggregate *across* categories with a **Weighted Geometric Mean** (categories are NOT substitutable — perfect docs cannot compensate for catastrophic reliability).
4. Apply **non-compensatory gates**: a blocker-severity issue caps the final score regardless of the base score.
5. Present as letter grade → radar chart → marginal-ROI list (progressive disclosure).

RESEARCH_05 demolishes the Maintainability Index (regression on 730k Java methods shows `locMI = 155.91 − 22.6·ln(LOC) − 0.1·LOC` reproduces MI for 99.7% of methods — MI is an obfuscated inverse size metric) and warns against **arithmetic averaging** of per-file scores (power-law distribution: thousands of trivial getters mask God classes). The SIG model replacement uses **risk-profile footprints** (distribution of LOC across risk bands), not means.

RESEARCH_01/RESEARCH_04 give the industry anchor: Technical Debt Ratio with the **A ≤5%, B ≤10%, C ≤20%, D ≤50%, E >50%** grid and a development cost of **30 min/LOC** — which Bragi's current `DebtThresholds` already mirrors. That part is correct and should be kept as the *Maintainability sub-axis*; the gap is everything around it.

## 2. Current state (gap)

`Asgard/Bragi/Ratings/services/ratings_calculator.py` (295 lines) + `Asgard/Bragi/Ratings/models/ratings_models.py` (100 lines):

- Three dimensions only (maintainability, reliability, security). Maintainability = debt-ratio grid (good, matches RESEARCH_01). Reliability and Security = **worst-severity-only** mapping (`critical→E … low→B`). A file with 400 medium bugs rates the same C as a file with one medium bug — no density signal, exactly the "gradient destruction" DEEPTHINK_01 warns about in §4.
- `overall_rating` = worst of the three dimensions (pure min). DEEPTHINK_01 §3: worst-case aggregation is "too pessimistic; fixing 9 of 10 bugs yields zero score improvement, demoralizing teams".
- No per-file ratings at all — only a project-level rating. RESEARCH_05's SIG model and DEEPTHINK_01's whole design are file-first, aggregated via risk profiles.
- Duck-typed `getattr` extraction of reports (`getattr(debt_report, "total_debt_hours", …)`) with silent `A` defaults when a report is missing — a missing security scan yields a perfect security grade. DEEPTHINK_14 calls this epistemological arrogance; absence of evidence must be communicated, not rewarded.
- No numeric continuous score, no category sub-scores, no gates, no ROI output, no uncertainty output.

## 3. Target state

A `CompositeScoreEngine` that produces, per file and per project:

```
FileQualityScore
├── utilities: Dict[MetricId, float]        # u ∈ [0,1] per metric
├── category_scores: Dict[Category, float]  # WAM within category
├── base_score: float                       # WGM across categories
├── cap: ScoreCap                           # gate applied (reason, ceiling)
├── final_score: float                      # min(base_score, cap.ceiling)
├── grade: LetterRating                     # A ≥.90, B ≥.80, C ≥.70, D ≥.60, E <.60
├── confidence: ScoreConfidence             # which inputs were present/missing
└── roi_actions: List[ROIAction]            # ranked ∂S/∂u improvement list
```

### 3.1 Utility mapping layer (DEEPTHINK_01 §1)

| Metric class | Transform | Formula |
|---|---|---|
| Count-based (bugs, smells, debt items, vulns) | Laplace density + exponential decay | `ρ = severity_weighted_count / (LOC + 200)`; `u = exp(−λ·ρ)` |
| Complexity | never sum across file; use max + mean | `u_max = exp(−k·max(CC_cognitive − T, 0))`, threshold T from language profile (15 default, 25 C-family per RESEARCH_07 findings relayed via RESEARCH_01) |
| Bounded % (type coverage, doc coverage, duplication) | linear | `u = pct/100` (duplication inverted) |
| LOC penalty | logistic decay | `u_LOC = 1 − 1/(1 + exp(−k·(LOC − 600)))`, `L_c = 600` |

Severity weights for the count-based numerator reuse the SQALE non-remediation factors from RESEARCH_04: **Blocker 1000, High 100, Medium 15, Low 10, Info 4** (normalized).

### 3.2 Category structure

Three pillars, mapping onto existing Bragi report sources:

| Category | Member metrics | Source module |
|---|---|---|
| Reliability | bug density, worst-severity gate input, thread-safety findings | `Bragi/Quality/BugDetection`, quality_report smells |
| Maintainability | debt ratio, max/mean cognitive complexity, duplication %, LOC penalty, cycle count | `Bragi/Quality` (debt), `Bragi/Dependencies` (cycles) |
| Comprehensibility | doc coverage, type coverage, naming quality | `Bragi/Quality`, Coverage reports |

Intra-category weights ship as static defaults (documented, config-overridable via `RatingsConfig`) with a documented upgrade path to PCA-derived weights (DEEPTHINK_01 §2) once the calibration pipeline of Plan 05 exists. Inter-category default weights: Reliability 0.45, Maintainability 0.35, Comprehensibility 0.20 (DEEPTHINK_01: "Reliability will naturally claim the highest weight").

### 3.3 Aggregation

```python
C_j = sum(w_i * u_i for each metric i in category j)      # WAM
S_base = prod(C_j ** W_j for each category j)             # WGM (weights sum to 1)
S_final = min(S_base, max_cap)
```

Non-compensatory gates (DEEPTHINK_01 §4):

| Condition | Cap | Resulting max grade |
|---|---|---|
| any Blocker/Critical bug or vulnerability | 0.59 | E is impossible to escape (F-equivalent) |
| max cognitive complexity > 50 | 0.69 | D |
| prohibited license in dependencies (Plan 03) | 0.69 | D |
| else | 1.0 | — |

The cap object records *why*, so the report can say "base score 0.87 (B) capped to 0.59 (E) by 1 Blocker vulnerability — fixing it restores B".

### 3.4 Project-level aggregation: risk profiles, not means

Per RESEARCH_05 (SIG model): the project score is **not** the mean of file scores. Compute a risk-profile footprint — % of total LOC residing in files graded A/B/C/D/E — and map footprints to a project grade with thresholds (defaults: project A requires ≥70% LOC in A/B files and 0% in E; project E when >20% LOC in E files; interpolate B/C/D). Keep the existing project debt-ratio grid as the Maintainability category input at project level.

### 3.5 Missing-input handling (DEEPTHINK_14)

Replace "no report → A" with `confidence` tri-state per dimension: `MEASURED`, `NOT_MEASURED`, `PARTIAL`. A `NOT_MEASURED` dimension is excluded from the WGM (renormalize remaining weights) and the grade is annotated: "Security: not assessed (no scan supplied)". `overall_rating` must never silently include defaulted-A dimensions.

## 4. Concrete file/module changes

All inside `Asgard/Bragi/Ratings/`:

| File | Change |
|---|---|
| `models/ratings_models.py` | Add `MetricUtility`, `CategoryScore`, `ScoreCap`, `ScoreConfidence`, `ROIAction`, `FileQualityScore`, `RiskProfile` pydantic models. Extend `ProjectRatings` with `composite_score: float`, `risk_profile: RiskProfile`, `file_scores: List[FileQualityScore]`, `confidence` fields. Keep `LetterRating`, `DebtThresholds` unchanged (backward-compatible). |
| `models/_scoring_models.py` (new) | House the new scoring models if `ratings_models.py` exceeds the repo's file-size conventions. |
| `services/utility_mapper.py` (new) | Pure functions: `count_to_utility(count, weighted, loc, lam)`, `complexity_to_utility(max_cc, mean_cc, threshold)`, `bounded_to_utility(pct)`, `loc_penalty(loc, l_c=600, k=0.01)`. Zero I/O, fully unit-testable. |
| `services/composite_score_engine.py` (new) | `CompositeScoreEngine.score_file(metrics: FileMetricBundle) -> FileQualityScore`; `score_project(file_scores) -> ProjectRatings` (risk-profile aggregation); gate application; weight renormalization for missing inputs. |
| `services/_roi_calculator.py` (new) | Finite-difference `∂S/∂u_i` per metric (the model is differentiable per DEEPTHINK_01 §5): for each metric compute score delta from a standard improvement step; rank descending; special-case cap-lifting actions ("Fix 1 Blocker → lifts E cap, grade becomes B"). |
| `services/ratings_calculator.py` | Becomes a thin adapter: extract metrics from report objects into `FileMetricBundle`s (replacing scattered `getattr` walks with one `_report_extractors.py`), delegate to `CompositeScoreEngine`, keep `calculate_from_reports()` signature working (existing consumers: `Asgard/Heimdall/cli/handlers/ratings.py`, `Asgard/MCP/server/_mcp_tools.py`, `Asgard/Bragi/QualityGate/services/quality_gate_evaluator.py`). |
| `services/_report_extractors.py` (new) | Typed extraction of DebtReport / quality report / SecurityReport → `FileMetricBundle`, recording which sources were present (feeds `ScoreConfidence`). |

## 5. Phased implementation

1. **Phase A — utility layer**: `utility_mapper.py` + models + unit tests (pure math, no integration risk).
2. **Phase B — engine**: `composite_score_engine.py` WAM/WGM + gates + risk-profile project aggregation; `ratings_calculator.py` delegates while preserving the legacy per-dimension `DimensionRating` outputs (computed from category scores) so `QualityGateEvaluator` and CLI handlers keep working.
3. **Phase C — confidence + ROI**: missing-input renormalization, `_roi_calculator.py`, rationale strings ("base 0.87 capped to 0.59 by …").
4. **Phase D — consumer upgrades**: `Heimdall/cli/handlers/ratings.py` prints grade + category radar values + top-5 ROI actions; `QualityGate` gains a `COMPOSITE_SCORE` MetricType.

## 6. Testing considerations

- Property tests for the math: `u` monotonic in inputs; WGM ≤ min-category bound behavior (score → 0 as any category → 0); cap never raises a score; renormalized weights sum to 1.
- Golden-value tests replicating DEEPTHINK_01 worked behaviors: 50-line file with 1 blocker vs 5000-line spaghetti with 1 blocker — both capped ≤0.59 but base scores differ and are visible.
- Small-file volatility regression: 1 smell in a 10-line file must not score worse than 20 smells in a 2000-line file (Laplace +200 smoothing).
- Backward-compat tests: existing `Asgard_Test/tests_Bragi/L0_Mocked/Ratings/test_ratings_calculator.py` must keep passing (same `ProjectRatings` surface, same debt-grid grades for the maintainability dimension).
- Explicit test: no security report supplied → `security.confidence == NOT_MEASURED` and overall excludes it (never a silent A).
