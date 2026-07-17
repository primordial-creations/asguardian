# 05 — Cohesion & Coupling Metrics (LCOM4, CBO/Ca/Ce/RFC, Multi-language)

**Sources:** `_Docs/Research/Completed/RESEARCH_06_cohesion_coupling_metrics.md`, `DEEPTHINK_01/02_solid_*` (LCOM4 as SRP proxy), `RESEARCH_03_sonarqube_solid_detection.md` (thresholds).

## Rationale

`Asgard/Bragi/OOP/` currently computes Python-only metrics via `ast`: `cohesion_analyzer.py` (LCOM), `coupling_analyzer.py` (CBO/Ca/Ce), `rfc_analyzer.py`, `inheritance_analyzer.py` (DIT/NOC), instability `Ce/(Ca+Ce)`. Research findings:

- **LCOM variant matters.** LCOM1 suffers the Lack-of-Discrimination Anomaly; LCOM2's forced zeroing masks fragmented classes; LCOM3 misses method-call edges and falsely penalizes delegation. **LCOM4 (Hitz & Montazeri)** — connected components over a graph whose vertices are methods+fields and whose edges are field-access *and* intra-class method invocation — is "the definitive structural proxy for SRP": LCOM4 = k literally means the class splits into k classes (RESEARCH_06). Verify/upgrade `_cohesion_helpers.py` to true LCOM4 semantics (include method→method call edges; exclude `__init__`-only artifacts; treat property accessors specially).
- **Coupling without a compiler is ~90% accurate** with the heuristic stack RESEARCH_06 documents: global symbol index → explicit import resolution (exact for Ca/Ce) → localized assignment type tracking (`ps = PaymentService(); ps.charge()` binds `ps`) → fallback name matching against the import index.
- **Multi-language** arrives free once plan 02's CIR exists — LCOM4 needs only `MethodInfo.all_identifiers ∩ ClassInfo.fields` and method-call name intersection.

## Target State

### Metric definitions (single doc + implementation source of truth)

| Metric | Definition | Threshold (flag) | Source |
|---|---|---|---|
| LCOM4 | connected components of method/field graph (field-share OR method-call edges), DFS count | >1 (with methods ≥ 4 to skip trivia) | RESEARCH_06 |
| LCOM5 (HS) | `(sum(mA)/a − m) / (1 − m)` density form — report-only, for trend continuity | >0.8 advisory | RESEARCH_06 |
| CBO | distinct classes referenced (fields, params, returns, instantiations, resolved method receivers) | >20 (SonarQube S1200 default; profile-tunable) | RESEARCH_03 |
| Ca / Ce | afferent/efferent module coupling from the plan-03 import graph (exact, no inference needed) | instability I = Ce/(Ca+Ce) reported per module | RESEARCH_06 |
| RFC | methods declared + distinct methods invoked (resolved via assignment tracking) | >50 advisory | RESEARCH_06 |
| WMC | Σ cyclomatic complexity of methods (reuse `Bragi/Quality` complexity) | >20 combined with LCOM4>1 → God-class signal | DEEPTHINK_02 |

### Algorithms

**LCOM4 (language-agnostic, CIR-based):**
```
vertices = methods ∪ fields
edges    = {(m, f) : f ∈ m.all_identifiers ∩ class.fields}
         ∪ {(m1, m2) : m2.name ∈ m1.all_identifiers and m2 ∈ class.methods}
LCOM4    = connected_components(vertices restricted to methods⊕their reachable fields)
```
Handle shadowing lexically: identifiers collected only when access pattern matches the language's self/this/receiver form (Python `self.x`, TS/Java `this.x`, Go receiver name) — the CIR extraction queries already capture receiver-qualified accesses.

**Heuristic reference resolution for CBO/RFC (RESEARCH_06 "Assignment Type Tracking"):**
1. Build/reuse the global symbol index from plan 03 (class name → file).
2. Within a method body: track `var = ClassName(...)` / `var: ClassName` / `var = new ClassName()` bindings in a local table.
3. `var.m()` → resolves to `ClassName` → CBO edge + RFC call. Unbound receivers fall back to matching `m` against methods of imported classes; ambiguous → no edge (precision over recall for coupling).

### Wiring into ratings & SOLID

- `evaluators/srp.py` (plan 02) consumes LCOM4 + WMC + import-root fan-out.
- Maintainability rating (`Bragi/Ratings`) may weight module instability trend from `Reporting/History` (advisory only; no gate).
- Report layer: per-class metric table with an `explanation` column (e.g. component membership lists) — actionability is the point of LCOM4.

## Concrete Changes

1. `Bragi/OOP/services/_cohesion_helpers.py`: implement/verify true LCOM4 (method-call edges; constructor/accessor exclusions); add LCOM5 for continuity; deprecate any LCOM1/2 outputs to "legacy" fields.
2. `Bragi/OOP/services/coupling_analyzer.py`: add assignment-tracking resolver; source Ca/Ce from the plan-03 module graph instead of recomputing imports.
3. NEW `Bragi/OOP/services/cir_metrics.py`: multi-language LCOM4/CBO over plan-02 CIR (behind `@with_ast_fallback`).
4. Thresholds into `Shared/Profiles` builtin profiles (`Asgard Way - Python`: CBO 20, LCOM4 1, WMC 20; Strict: CBO 12).
5. CLI: `heimdall oop cohesion <path> --explain <Class>` prints the component partition.

## Testing

- Golden fixtures: cohesive class (LCOM4=1), two-island class (=2), delegation class where helper methods are only connected via calls (=1 — the LCOM3-vs-LCOM4 regression test).
- Coupling fixture: class instantiating 21 distinct types triggers CBO; stdlib exclusion list honored (configurable whether stdlib counts, default: count — matches SonarQube S1200 aggressiveness, profile can relax).
- Cross-language: identical Java/Python/TS fixture classes produce identical LCOM4.
- Accuracy sample: run against a real mid-size OSS repo and manually verify ≥90% of CBO edges vs an LSP-based ground truth on a 50-class sample (RESEARCH_06's expected heuristic accuracy).
