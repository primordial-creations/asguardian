# Plan 03 — Performance: Route Archetypes, Lab-Proxy Budgets, Warn/Fail Gates

**Priority:** P1
**Primary research:** DEEPTHINK_02 (context-calibrated budgets), DEEPTHINK_03 (lab-vs-field epistemics)
**Depends on:** Plan 01 (severity mapping, gate); Plan 06 (config file to hold budgets)

---

## 1. Rationale (research-backed)

Current state (`Asgard/Freya/Performance/`):

- `services/page_load_analyzer.py` + `_page_load_helpers.py` grade LCP/FCP/CLS/TTFB with **universal** linear formulas (e.g. `lcp_score = 100 − LCP/50`) and Google's global cut-points, then blend them into one 0–100 score → letter grade (`score_to_grade`).
- The code still measures/grades **FID**, deprecated in favor of INP (flagged in 00_Overview; RESEARCH_02 pending).
- `resource_timing_analyzer.py` collects resource timings but no budget machinery exists — no per-route targets, no warn/fail distinction, no TBT.
- Nothing in the output says the numbers are synthetic. DEEPTHINK_03 is blunt: headless CI boxes have no GPU (software rasterization inverts costs), no VSync, x86-vs-ARM mismatch — absolute lab numbers are **weak evidence**; the delta and the *inputs* (payload weights, blocking scripts) are what a lab can measure honestly.

DEEPTHINK_02 prescribes:
1. **Route archetypes** — Document (`LCP < 1.0s`, `CLS 0.00`), Transactional (`< 2.5s`, `< 0.05`), Rich App (`< 4.0s`, `< 0.15`) — universal thresholds are simultaneously too lenient for static pages and unrealistic for SPAs.
2. **Lab proxies in CI, not field metrics** — budget **TBT** (under CPU throttling) instead of INP; budget LCP *inputs*: total image weight, render-blocking scripts, font payload.
3. **Warn vs Fail dual thresholds** — soft budget warns (mergeable, acknowledged), hard budget fails (catastrophic ceiling, e.g. JS payload > 2MB). Binary gates drive metric-gaming (skeleton-screen abuse, setTimeout-chunking that slows total wall-clock).
4. **Exemption tags** (`[perf-override-async]`-style) — a formal escape hatch so business-accepted tradeoffs don't force gaming.

## 2. Target state

Performance analysis takes a **route archetype** (explicit or heuristically guessed), evaluates lab-proxy metrics against per-archetype **soft/hard budgets** from a budget config, emits WARN/FAIL findings into Plan 01's pipeline, and labels every metric surface "Lab Data — Synthetic Baseline".

## 3. Concrete changes in `Asgard/Freya/Performance/`

### 3.1 Models (`models/performance_models.py` + new `models/_budget_models.py`)

```python
class RouteArchetype(str, Enum):
    DOCUMENT = "document"; TRANSACTIONAL = "transactional"; RICH_APP = "rich_app"

class BudgetThreshold(BaseModel):
    metric: str            # "lcp_ms" | "cls" | "tbt_ms" | "js_bytes" | "image_bytes" | "font_bytes" | "render_blocking_count"
    soft: Optional[float]  # warn above this
    hard: Optional[float]  # fail above this

class RouteBudget(BaseModel):
    archetype: RouteArchetype
    thresholds: List[BudgetThreshold]
    exemptions: List[str] = []   # metric names formally exempted, with reason in exemption_reasons
    exemption_reasons: Dict[str, str] = {}

class BudgetEvaluation(BaseModel):
    metric: str; value: float; soft: Optional[float]; hard: Optional[float]
    status: Literal["pass", "warn", "fail", "exempt"]
```

Default budget table (data constant, from DEEPTHINK_02 §Step-1 exactly): Document LCP soft 1000/hard 2500, CLS soft 0.0/hard 0.1, TBT soft 100/hard 300; Transactional LCP 2500/4000, CLS 0.05/0.25, TBT 150/600; Rich App LCP 4000/6000, CLS 0.15/0.25, TBT 150/600. Payload budgets (all archetypes to start): JS hard 2 MB (DEEPTHINK_02's example ceiling), soft 1 MB; images soft 1.5 MB; fonts soft 300 KB; render-blocking scripts soft 3.

### 3.2 TBT measurement (`services/_page_load_helpers.py` / `page_load_analyzer.py`)

Add long-task capture to `_extract_web_vitals`'s injected JS: `new PerformanceObserver(...).observe({type: 'longtask', buffered: true})`; `TBT = Σ max(0, duration − 50ms)` between FCP and interactive-settle (use existing networkidle wait as the window end — document the approximation). Optional CPU throttling via CDP `Emulation.setCPUThrottlingRate` (Chromium only; expose `cpu_throttle: float = 4.0` on `PerformanceConfig`, skip silently on other engines).

**FID:** stop grading it (keep the field populated if observed, marked `deprecated`); do not add INP grading until RESEARCH_02 lands — lab INP is ill-defined without scripted interactions.

### 3.3 Archetype detection (`services/_archetype_detector.py`, new)

Explicit archetype always wins (per-route in budget config, Plan 06). Heuristic fallback:
- RICH_APP if: SPA markers (root `<div id="root|app">` with < 5 initial DOM text nodes, large JS/HTML byte ratio > 4, history-API routing detected).
- DOCUMENT if: text-dominant (text bytes / total DOM nodes high), no forms beyond search, `<article>`/heading density.
- Else TRANSACTIONAL. Report always states which archetype was applied and why ("archetype: rich_app (heuristic — override in budget config)").

### 3.4 Budget evaluator (`services/budget_evaluator.py`, new)

Pure function: `(PageLoadMetrics, ResourceTimingReport, RouteBudget) -> List[BudgetEvaluation]`. Status: exempt → pass-with-note; value > hard → fail; > soft → warn. Feeds Plan 01: fail → CRITICAL finding, warn → MAJOR (see Plan 01 §3.3 — no performance Blockers, per DEEPTHINK_03's weak-evidence stance).

### 3.5 Scoring & labeling

- Replace the blended linear score in `calculate_score` with: per-archetype normalized score derived from budget headroom (`100 × mean(clamp(1 − (value − soft)/(hard − soft)))` over budgeted metrics), keeping the existing function signature; `score_to_grade` retained.
- Every formatter (`cli/_formatters_performance.py`) and report model gains the header: **"Lab Data — Synthetic Baseline. These metrics measure code structure under a controlled environment; they are strong evidence for regressions (deltas), weak evidence for real-user experience. Use RUM for field truth."** (DEEPTHINK_03 §Communicating).
- Metric deltas vs a stored previous run (simple JSON snapshot beside output, `performance_baseline.json`) get first-class display — the delta is the lab's ground truth (DEEPTHINK_03 §3).

## 4. Phased steps

1. **Phase A:** budget models + evaluator + default tables (pure Python, fully unit-testable).
2. **Phase B:** TBT capture + FID deprecation + throttling option.
3. **Phase C:** archetype detector + report integration + Lab-Data labeling.
4. **Phase D:** severity mapping into Plan 01 gate; delta snapshot.
5. **Phase E (post-RESEARCH_02):** INP strategy, threshold recalibration.

## 5. Testing notes

- New `Asgard_Test/tests_Freya/L0_Mocked/Performance/` (currently absent — Plan 07): budget evaluator matrix (pass/warn/fail/exempt × missing soft/hard), TBT arithmetic from synthetic long-task lists, archetype heuristics on canned page-signal dicts, score-from-headroom bounds (0–100), grade mapping.
- Contract test: `PerformanceReport` JSON round-trip with and without new optional fields.

## 6. Thin-research flags

- **RESEARCH_02 (pending):** INP replacement design, 2024-25 CWV threshold updates — Phases A–D are built so only the data tables and one new metric extractor change.
- Persona-segmented percentiles (DEEPTHINK_02 §2) are a RUM concern — out of scope for a lab tool; the Lab-Data disclaimer explicitly hands this off.
- Guardrail custom metrics (`performance.mark` ingestion) noted as future work; needs a config schema decision in Plan 06 first.
