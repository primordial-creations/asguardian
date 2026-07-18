# 10 — Evaluation, Benchmarking & Confidence Calibration

**Sources:** `_Docs/Research/Heimdall/Completed/DEEPTHINK_06` (SAST evaluation methodology), `DEEPTHINK_03` §5 (calibration), `RESEARCH_01` (benchmark corpora, RealVuln, LLM post-filtering), `RESEARCH_02` (xAST/PyVul recall realities).

## Rationale

Heimdall has no measurement layer: no corpus, no precision/recall numbers, no calibration of the `confidence` field that already exists on `SecurityFinding`/`TaintFlow`. Without this, every rule change is a guess and the confidence buckets (plans 04/06) are meaningless — "0.8 confidence" is only valid if ~80% of 0.8 findings are true positives (DEEPTHINK_03 §5). Research also warns of overfitting: tools that "teach to Juliet's `bad()` functions" collapse on real code (RESEARCH_01: Semgrep 17.5% recall on RealVuln; RESEARCH_02: CodeQL 10.8% / Pysa 0% on PyVul). So the corpus must be realistic and temporally held out.

## Target State — `Heimdall_Test/evaluation/`

### 1. Corpus construction (DEEPTHINK_06 §2, RESEARCH_01)
- **Annotated fixtures** (`benchmarks/<domain>/<lang>/`): Semgrep-style `# ruleid:` / `# ok:` markers — the fast inner-loop gate every migrated rule feeds (plans 01–07). Include *semantic-perturbation* variants (rename vars, extract sink to helper, wrap source in redundant decorator) to catch memorized-regex behavior.
- **Real-world holdout**: a curated set of OSS Python repos + CVE pre-fix/post-fix pairs (mirroring RealVuln/PyVul intent), stored as references (commit SHAs + patch line spans), not vendored. 50 CVE repos establish the recall denominator (must-find TPs = AST nodes touched by the fix); 50 clean repos for precision sampling.
- **Stratification**: framework (40% Django, 30% FastAPI/Starlette, 15% Flask, 15% non-web) × maturity (30% enterprise, 50% mid, 20% hobbyist). Temporal-holdout ≥50% created after the rule-freeze date to expose overfitting.

### 2. Metric computation (DEEPTHINK_06 §3)
- **Deduplicate** raw alerts to semantic instances by `(file, target_sink_ast_node, cwe)` — multiple paths to one sink = 1 TP (matches plan-04 dedup).
- **Spatial match** via AST bounding boxes: a report matches ground truth if its line falls within the GT AST node span (fallback ±3 lines). No brittle exact-line matching.
- **Recall** on the 50 CVE repos; **precision** via a bounded manual-adjudication sample (n≈300) on clean repos (hybrid adjudication solves the unlabeled-positives problem — don't penalize real zero-days the tool finds as FPs).
- **Alert density**: FP per 10k LOC.
- **F-beta by profile**: report $F_{0.5}$ (CI/developer) and $F_2$ (audit) separately.

### 3. Acceptance thresholds (DEEPTHINK_06 §4) — CI gate for the analyzer itself
- Profile A (blocking dev PRs): precision ≥60%, recall ≥35%, $F_{0.5}$≥0.52, ≤2 FP/10k LOC.
- Profile B (async audit): precision ≥20%, recall ≥75%, $F_2$≥0.50, ≤15 FP/10k LOC.
- **Overfit rejection**: any rule whose recall drops >20% on the temporal holdout vs its fixture benchmark is rejected regardless of headline score.

### 4. Confidence calibration (DEEPTHINK_03 §5)
Pipeline that makes the buckets honest:
1. Run the engine over the corpus; record `(raw_confidence, ground_truth_bool)` per finding.
2. **Reliability diagram**: bin scores into deciles, plot predicted vs empirical TP rate; perfect = y=x.
3. If monotonic-but-miscalibrated, fit **isotonic regression** (or Platt scaling) as a final calibration layer converting raw heuristic scores → true probabilities. Persist the fitted map; apply before bucketing.
4. Track **Brier score** (mean squared error of probability vs outcome) as the core KPI. **Any new/changed rule must not worsen the Brier score** on the corpus before merge — the objective gate that keeps confidence trustworthy.

### 5. Optional LLM post-filter research track (RESEARCH_01/15, informational)
Document (not mandate) the "sift the noise" pattern: high-recall deterministic pass → LLM semantic triage can cut FP ~92%→~6%, but risks suppressing true positives with weaker models. If pursued, it sits *after* calibration as a separate confidence adjuster, never replacing the deterministic engine, and must itself be measured against the same corpus.

## Concrete Changes
- `Heimdall_Test/evaluation/`: `corpus/` (fixtures + CVE manifest JSON), `runner.py` (scan → dedup → AST-bbox match → metrics), `calibration.py` (reliability diagram + isotonic fit + Brier), `report.py`.
- CI job `heimdall-eval` (nightly + on-rule-change): fails PRs that regress F-beta, alert density, or Brier score.
- `Security/normalization` (plan 06) loads the fitted calibration map to convert raw→calibrated confidence before bucketing.
- Contribution docs: "no new rule without benchmark fixtures + non-regressing Brier."

## Testing / Bootstrapping
- Seed `benchmarks/` from the fixtures each of plans 01–08 already require, so the corpus grows with the work rather than as a separate effort.
- Golden metric test: a synthetic corpus with known TP/FP counts yields exactly the expected precision/recall/F-beta (validates the runner before trusting it on real data).
- Calibration unit test: a deliberately overconfident synthetic scorer is corrected toward y=x by isotonic regression and its Brier score drops.
