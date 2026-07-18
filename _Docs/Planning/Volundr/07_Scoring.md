# Volundr Upgrade Plan — 07 Composite Scoring & Posture Index (Cross-Cutting, P1)

**Scope:** replace every per-module `calculate_best_practice_score` with one shared, adversarial scoring engine; add an optional portfolio-level posture index.
**Research basis:** DEEPTHINK_05 (four-dimension composite score, security veto, defect density, environment profiles, prior art: CodeClimate/SonarQube), DEEPTHINK_01 (Graph-Weighted Posture Index, L3-norm aggregation, dilution/sea-of-lows defenses), RESEARCH_08 (Polaris weighted-sum formula, AWS Security Hub proportional model, Wiz/Orca graph-based context scoring).

---

## 1. Why (Research Rationale)

Current state: each module has a private additive percentage —
- K8s: `manifest_generator_helpers.py::calculate_best_practice_score` (20/25/20 per container + 15 NetPol + 10 Service + 10 PDB);
- CICD: `pipeline_generator_helpers.py` (triggers 20, >1 stage 20, concurrency 15, caching 15, env 15, timeout 15);
- Dockerfile: `dockerfile_generator.py::_calculate_best_practice_score`; similar in Terraform/Helm/Kustomize/GitOps/Compose helpers.

Failure modes these exhibit, per research:
1. **Collusion** (DEEPTHINK_05 §1A): the generator scores its own config; e.g. the CICD score reads `config.concurrency`, not the rendered YAML. A high score means "the generator did what it was programmed to do."
2. **Normalization trap** (§1B): naive passed/total means a 1-resource manifest and a 40-resource stack both "90%" with wildly different risk.
3. **Sea of lows / dilution** (DEEPTHINK_01 §1B/E): adding trivially-passing resources or fixing many LOWs outscores fixing one CRITICAL; linear sums invite Goodhart gaming.
4. **Verbosity trap** (DEEPTHINK_05 §1D): rewarding explicit declarations (e.g. Terraform "has locals/outputs" weights) teaches boilerplate farming.
5. **No security floor:** today a K8s manifest with root + writable rootfs can still score ≥ 50 via probes/limits/service points. DEEPTHINK_05 §3 requires security as a *veto* dimension.

## 2. Target State

### 2.1 Artifact-level composite score (all modules)

Computed **only from Validation-engine findings on rendered output** (plan 06), never from the input config:

1. **Per-logical-resource defect density** (DEEPTHINK_05 §1B): score each logical resource (K8s object, Terraform resource block, Compose service, pipeline job, Dockerfile stage) via subtractive severity penalties — CRITICAL −20, HIGH −10, MEDIUM −5, LOW −2, INFO 0 — floor 0, from a base of 100. Artifact score = mean of resource scores.
2. **Four dimensions** (DEEPTHINK_05 §3), each a sub-score from category-tagged findings:
   - **Security** (veto): any un-suppressed CRITICAL security finding caps the composite at 50; any HIGH caps at 70.
   - **Operability**: probes, PDB, HA, resource requests/limits, healthchecks, restart policies.
   - **Completeness**: unresolved placeholders/TODOs, required-but-missing variables; expected to be imperfect at generation time (the "nutrition label", DEEPTHINK_05 §2 Phase 1 — surfaced as a to-do checklist, not a failure).
   - **Maintainability** (lowest weight): naming, labels/tags (`owner`, `cost-center`), descriptions, DRY.
3. **Environment profiles** (DEEPTHINK_05 §3 "Configurability is mandatory"): `sandbox|development|staging|production` weight sets. A minikube chart is not graded F for missing PDB; production weights operability fully. Profiles adjust **weights**, never rule truth — dev/prod parity of generated structure is preserved (DEEPTHINK_02 conclusion).
4. **Letter grades** (CodeClimate model): A ≥ 90, B ≥ 80, C ≥ 65, D ≥ 50, F < 50, reported per-dimension (`Security: A, Operability: C`) plus remediation hints with effort estimates ("add resources block — 1 edit", SonarQube time-debt idiom).
5. **Suppressed findings** score as **passed** (mirrors AWS Security Hub suppression semantics, RESEARCH_08) but are counted separately in the report (`suppressed_count`, listed receipts) so posture debt stays visible without punishing documented risk acceptance.
6. **Anti-gaming clauses:**
   - Signal-to-noise: mild penalty for explicitly declaring values identical to secure provider defaults (DEEPTHINK_05 §1D) — schema-aware via Tier-2/ICM;
   - Cleverness whitelist: never penalize `for_each`/`count`/`dynamic`/YAML anchors (essential complexity, §1C);
   - Zero-edge resources get near-zero weight in any aggregate (dilution defense, DEEPTHINK_01 §1B).

### 2.2 Delta mode (post-edit guardrail)

`volundr score --baseline old.json` reports Δ per dimension: "edit lowered Security 90→60 because 0.0.0.0/0 ingress added" (DEEPTHINK_05 §2 Phase 2). Baselines are the serialized `ScoreReport`.

### 2.3 Portfolio posture index (GWPI — optional, later phase)

For multi-artifact projects (Scaffold output, GitOps repos), implement DEEPTHINK_01's model:
- Resource graph from cross-references (Service→Deployment selectors, Compose `depends_on`, TF `depends_on`/interpolations, pipeline job `needs`); centrality weights `w_i` (PageRank), normalized Σw=1.
- Finding risk `s_ij ∈ [0,1)` mapped from severity (CRITICAL 0.85, HIGH 0.6, MEDIUM 0.4, LOW 0.15 — CIS-style lateral-movement priors, DEEPTHINK_01 §1A).
- Resource risk `R_i = max(U_i, 1 − Π(1 − p_ij))` with epistemic floor `U_i` (0.4 if only Volundr static rules ran, lower when external tools also ran — "buy down uncertainty", §1C).
- System risk `ρ = (Σ w_i · R_i³)^(1/3)` (L3-norm weakest-link dominance, §1E); Posture = 100·(1−ρ).
- Document the three invalidating assumptions (ClickOps divergence, cross-domain linkage, independence fallacy — DEEPTHINK_01 §3) in the report footer; temporal multiplier τ(t) is out of scope until Volundr persists finding history.

## 3. Concrete Changes in `Asgard/Volundr/`

| Change | Files |
|---|---|
| New scoring engine: `ScoreReport` model (dimensions, grades, per-resource table, remediation list, suppressed receipts), density math, veto logic, environment weight profiles | new `Validation/models/score_models.py`, `Validation/services/scoring_engine.py`, `Validation/services/scoring_profiles.py` |
| Delete/deprecate per-module scorers; `Generated*` result models keep `best_practice_score: float` for backward compat (filled from composite) and gain `score_report: ScoreReport` | `Kubernetes/services/manifest_generator_helpers.py`, `CICD/services/pipeline_generator_helpers.py`, `Docker/services/dockerfile_generator.py`, `Docker/services/compose_generator.py`, `Compose/services/*`, `Terraform/services/_module_builder_blocks_part2.py`, `Helm/*`, `Kustomize/*`, `GitOps/*` helpers |
| `is_production_ready` (`kubernetes_models.py:124`) redefined: Security grade ≥ B AND composite ≥ 80 AND zero un-suppressed CRITICAL | each `Generated*` model |
| Graph builder + GWPI (phase 2) | new `Validation/services/resource_graph.py`, `posture_index.py` |
| CLI: `volundr score <path> [--environment prod] [--baseline report.json] [--format cli|json|sarif]` | `cli/_parser_commands_2.py`, new handler |

## 4. Phased Steps

1. **Phase A:** scoring engine over Validation findings; wire K8s + CICD + Dockerfile generators (highest-drift modules); keep legacy numbers populated.
2. **Phase B:** remaining modules (Terraform via evaluated-state awareness — score what the provider default gives, not lexical text); environment profiles; delta mode; letter-grade CLI rendering.
3. **Phase C:** resource graph + GWPI for Scaffold/GitOps multi-artifact outputs.

## 5. Testing Notes (adversarial, per DEEPTHINK_01 §1 / DEEPTHINK_05 §1)

- **Dilution test:** add 50 trivially-secure ConfigMaps to a fixture with one CRITICAL — composite and posture must not improve materially.
- **Sea-of-lows test:** fixing 20 LOW findings while 1 CRITICAL remains must not lift composite above the veto cap (50).
- **Veto test:** privileged container ⇒ composite ≤ 50 regardless of other dimensions.
- **Verbosity test:** adding redundant explicit defaults must not raise (and may slightly lower) Maintainability.
- **Profile test:** identical manifest scores differently under `sandbox` vs `production` profiles only via weights (rule outcomes identical).
- **Suppression test:** suppressed CRITICAL lifts the veto but appears in `suppressed_receipts`; report totals reconcile.
- **Determinism:** same artifact ⇒ identical `ScoreReport` (snapshot/golden tests); property-based test that any added finding never increases a dimension score.
- Extend `L8_Performance`: scoring a 200-resource rendered stack < 1s (Polaris-class linear pass, RESEARCH_08).

## 6. Doc Reconciliation

- All four module docs (`Kubernetes-Module.md`, `Terraform-Module.md`, `Docker-Module.md`, `CICD-Module.md`) contain per-module weight tables that will be obsolete — replace with a single link to a new `Scoring.md` page describing dimensions, veto, grades, environment profiles, and delta mode.
- `Overview.md` "Best Practice Scoring" table likewise.
