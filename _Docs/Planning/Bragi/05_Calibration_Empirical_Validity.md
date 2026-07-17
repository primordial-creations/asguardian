# Plan 05 — Threshold Calibration, Language Profiles, and Empirical Validity

**Priority: P2** — the upgrade path Plan 01 explicitly defers to ("PCA-derived weights once the calibration pipeline of Plan 05 exists"); converts Bragi from hardcoded dogma to data-backed thresholds.
**Research basis:** `_Docs/Research/Bragi/Completed/DEEPTHINK_10` (SZZ pipeline, ZINB/SHAP models, LOC+churn controls, Bayesian cold start), `DEEPTHINK_02` §4 (percentile calibration, project-relative norms), `DEEPTHINK_04` (language profiles, AST mass, P90 baselines), `RESEARCH_02` (CK metric predictive power: keep WMC/CBO/RFC, drop DIT/NOC; Shatnawi thresholds WMC=20, CBO=9), `RESEARCH_06` (ground-truth benchmarks, inter-rater ceiling: 60–70% max precision for subjective smells), `RESEARCH_09` (change coupling beats static structure; ISP violations most damaging day-to-day).

---

## 1. Rationale (what the research says)

- DEEPTHINK_10 is blunt: when models control for **LOC and churn**, the predictive power of most classic structural metrics "collapses to near zero"; process metrics dominate. A metric earns its place in Plan 01's utility set only with *incremental* predictive power over file size. It also warns thresholds are temporally and linguistically non-portable — a Java-calibrated CC threshold "actively penalizes developers for writing safe code" in Go.
- DEEPTHINK_02 §4 / DEEPTHINK_04: thresholds should be **population percentiles** (P90–P95 of the language corpus), and ultimately **project-relative** — "define a smell as a statistical anomaly relative to the team's own habits" — with test files excluded from the distributions (Plan 04's classifier provides this). DEEPTHINK_04's concrete mechanism: per-language YAML profiles as the single calibration plane, updateable without code changes.
- RESEARCH_02 settles metric selection: WMC, CBO, RFC are the defect-prediction gold standard; DIT/NOC are negative-ROI; LCOM-family is advisory-only (high FP). Defaults exist (WMC 20, CBO 9) for the cold-start profile.
- RESEARCH_06: for heuristic smells, expert inter-rater agreement caps achievable precision at 60–70% — calibration should therefore optimize *alignment with this project's developers* (suppression telemetry from Plan 04, PR-comment resolution behavior), not chase 100% precision against a universal oracle.
- RESEARCH_09: evolutionary change coupling (files that co-change) predicts defects better than static coupling — the friction collector Plan 02 builds for interest calculation is reusable as the strongest calibration feature.
- DEEPTHINK_10's full auto-calibration (SZZ + ZINB/XGBoost+SHAP) needs 200–300 traceable bug-fix commits (12–24 months of history); below that, use the Bayesian prior = shipped language profiles.

## 2. Current state (gap)

- Every threshold in Bragi is a hardcoded constant: `DebtThresholds` grid, complexity limits in `complexity_models.py`/`_generic_complexity.py`, `DependencyConfig.max_dependencies=10 / max_dependents=15`, naming/documentation limits — none carry provenance, language-specificity, or a recalibration path.
- `Quality/languages/*` has 10 language analyzers, but thresholds do not vary by language: idiomatic Go error handling and Python comprehension density are judged on the same numbers, the exact failure DEEPTHINK_10 and DEEPTHINK_04 describe.
- No local-distribution measurement: Bragi cannot tell a user "your P95 method length is 42; this method is 130" — the most defensible sentence a quality tool can utter (DEEPTHINK_02).
- No feedback loop of any kind: rules never lose weight when they prove worthless on this codebase, and Plan 01's intra-category weights stay static guesses forever without this plan.

## 3. Target state

### 3.1 Language profile plane (`Bragi/Calibration/profiles/*.yaml`, new)

Per DEEPTHINK_04's Tier-3 design — one YAML per supported language, the single source of thresholds:

```yaml
# Bragi/Calibration/profiles/python.yaml
language: python
provenance: "corpus P90/P95, top OSS repos, 2025 snapshot"   # DEEPTHINK_10: time-stamped validity bounds
thresholds:
  cognitive_complexity: {warn: 15, fail: 25}
  cyclomatic_complexity: {warn: 10, fail: 20}
  method_ast_mass_p90: 120
  wmc: 20              # RESEARCH_02 / Shatnawi
  cbo: 9
  max_efferent: 10
  max_afferent_percentile_gate: 0.95
severity_confidence:
  global_dead_code: LOW      # dynamic language → demote to INFO (DEEPTHINK_04 §4)
```

- Loader `LanguageProfileService` with a documented fallback chain: project override → language profile → generic defaults. All analyzers (Quality, OOP, Dependencies, Ratings utility thresholds from Plan 01 §3.1) read through it; hardcoded constants become the generic-defaults layer.
- `severity_confidence` implements DEEPTHINK_04's confidence-weighted severity (provable-in-static-languages vs heuristic-in-dynamic findings), which Plan 04's presenter renders as FACT vs HEURISTIC.

### 3.2 Local percentile calibrator (`Bragi/Calibration/services/local_calibrator.py`, new)

DEEPTHINK_02's "ultimate evolution", runnable as `asgard bragi calibrate <path>`:

1. Scan the project (reusing Quality's metric extraction; PRODUCTION context only via Plan 04's classifier; exclude generated).
2. Compute the empirical CDF per metric; derive P90/P95 anchors.
3. Emit `.asgard_cache/bragi_local_profile.yaml` (same schema, `provenance: "local P95, <date>, n=<files>"`), which sits atop the fallback chain.
4. Guardrails: refuse to calibrate below a minimum sample (default 200 functions per metric); clamp local thresholds to ±50% of the language profile so a uniformly bad codebase cannot normalize its own rot (the DEEPTHINK_11 deviance concern applied to statistics).

### 3.3 Rule validity scoring (`Bragi/Calibration/services/rule_validator.py`, new; opt-in)

DEEPTHINK_10's Heimdall-Quality framework, phased honestly:

- **Stage 1 (cheap, no tracker needed)**: reuse Plan 02's `_git_friction.py` bugfix-commit heuristic. For each rule, compare violation density in files subsequently touched by bugfix commits vs not, controlling for LOC by comparing within size deciles. Output per-rule `ValidityReport {lift, n, verdict: PREDICTIVE | NEUTRAL | UNKNOWN}`.
- **Stage 2 (full SZZ, needs history)**: `git blame` the fix-commit hunks to origin commits; time-travel metric measurement at the pre-bug revision; ZINB or gradient-boosted model with LOC+churn as mandatory controls, SHAP for attribution. Gate on the burn-in rule: ≥ 15 events per candidate rule (~200–300 traceable fixes); below it, report `UNKNOWN` and keep priors.
- Consequences are conservative by design: `NEUTRAL` rules are *demoted one channel* (Plan 04: ci_gate→pr_review→dashboard) and their Plan 01 intra-category weight is scaled down — never silently deleted; the report says why.
- Weight derivation for Plan 01: PCA on the project's metric matrix to collapse collinear utilities (DEEPTHINK_01 §2's promised upgrade), emitted into the local profile as `category_weights`, consumed by `CompositeScoreEngine` when present.

### 3.4 What stays out of scope

Cross-project corpus mining (DEEPTHINK_02's 5,000-repo pipeline) is not something a self-contained pip package should do at runtime; shipped language profiles are maintained offline by the Asgard project itself. Document this boundary in the profile provenance field.

## 4. Concrete file/module changes

| File | Change |
|---|---|
| `Asgard/Bragi/Calibration/` (new package) | `models/calibration_models.py` (`LanguageProfile`, `ThresholdSpec`, `ValidityReport`), `profiles/*.yaml` (python, go, javascript, typescript, java, csharp, cpp, ruby, php, rust, shell — seeded from current hardcoded values + RESEARCH_02 anchors), `services/profile_service.py`, `services/local_calibrator.py`, `services/rule_validator.py`. |
| `Quality/models/complexity_models.py`, `_generic_complexity.py`, `Quality/languages/*/services/_*_rules.py` | Threshold reads route through `LanguageProfileService` (constants kept as generic-default layer). |
| `Ratings/services/utility_mapper.py` (Plan 01) | Thresholds (`T`, `λ`, `L_c`) resolved per language profile instead of module constants. |
| `Ratings/services/composite_score_engine.py` (Plan 01) | Accept optional `category_weights`/intra-weights from local profile. |
| `OOP/services/*` | WMC/CBO/RFC thresholds from profile; mark DIT/NOC outputs `advisory` (RESEARCH_02) rather than deleting them. |
| `Heimdall/cli/handlers/` | New `calibrate` and `validate-rules` commands (thin wrappers). |

## 5. Phased implementation

1. **Phase A — profile plane**: schema, loader, YAML seeds from existing constants (pure refactor, zero behavior change by construction), then language-differentiated values (Go CC, Python comprehension mass) in a second commit.
2. **Phase B — local calibrator**: CDF computation, guardrailed local profile, CLI command.
3. **Phase C — validity stage 1**: friction-based lift report; channel demotion wiring into Plan 04.
4. **Phase D — validity stage 2 + weights**: SZZ pipeline, burn-in gating, PCA weight emission into Plan 01.

## 6. Testing considerations

- Loader: fallback-chain resolution order property test; missing profile → generic defaults, never KeyError.
- Refactor safety (Phase A): full existing `Asgard_Test/tests_Bragi` suite must pass unmodified against the YAML-routed thresholds — this *is* the test that the refactor changed nothing.
- Calibrator: synthetic project with known metric distribution → P95 within tolerance; sub-sample project → refusal message; pathological project (all functions CC=40) → clamp engages.
- Validator stage 1: seeded fixture repo (violations planted in files with synthetic bugfix history) → PREDICTIVE; shuffled labels → NEUTRAL/UNKNOWN; assert LOC-decile control prevents a pure size proxy from scoring PREDICTIVE (the DEEPTHINK_10 confounder test — most important test in this plan).
- Determinism: same repo state → identical local profile bytes (stable sort, fixed seeds for PCA sign convention).
