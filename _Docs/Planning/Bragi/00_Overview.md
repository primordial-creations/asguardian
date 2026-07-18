# Bragi Upgrade Plan — Overview

Bragi is Asgard's code-analysis brain: **Ratings** (letter grades, composite quality) and **Dependencies** (import graph, SBOM, license, requirements), sitting atop the Quality/OOP/Architecture/Coverage analyzers whose reports it aggregates and the QualityGate that enforces them. This plan set is derived from 32 completed research documents (`_Docs/Research/Bragi/Completed/`: DEEPTHINK_01–14, RESEARCH_01–18), the intent docs (`_Docs/Asgard/Asgard.md`, `Asgard Package.md`, `_Docs/Asgard/Heimdall/Ratings-Module.md`/`QualityGate-Module.md` — written pre-split, when these modules lived under Heimdall), and a review of the current source under `Asgard/Bragi/`.

## Executive summary

The research converges on one theme: **Bragi currently computes plausible-looking numbers with unsound machinery.** The ratings are worst-severity lookups rather than a real scoring model (a file with 400 medium bugs grades identically to one with a single medium bug); technical-debt hours are linear sums of guessed constants against a dev-cost denominator that is ~50× off the industry anchor; the license checker can mark LGPL as prohibited via substring matching; emitted purls are spec-invalid; missing scan inputs silently produce perfect grades and passing gates. The intended state — per DEEPTHINK_01's hierarchical gated geometric model, RESEARCH_04's SQALE machinery, and RESEARCH_15/DEEPTHINK_09's differential architecture — is a calibrated, uncertainty-honest, context-aware scoring system whose every output carries its rationale, and a quality gate that judges *new* code rather than punishing history.

Six plans. 01 and 02 (pre-existing, kept unchanged) rebuild the scoring and debt cores. 03 fixes Dependencies and turns its graph into the centrality/license provider the other plans consume. 06 makes the gate differential and epistemically honest. 04 adds context profiles (test/generated code) and trustworthy presentation/governance. 05 replaces hardcoded thresholds with language profiles and a local calibration/validation pipeline.

## Gap analysis — current vs intended

| Area | Current (`Asgard/Bragi/`) | Intended (research-backed) | Plan |
|---|---|---|---|
| Overall rating | Worst-of-three-letters; per-dimension = worst single severity; no per-file scores | Utility mapping → WAM within categories → WGM across → non-compensatory caps; per-file scores aggregated by SIG risk-profile footprints; ROI action list (DEEPTHINK_01, RESEARCH_04/05) | 01 |
| Missing inputs | No report → silent grade A; gate metric absent → condition passes | Tri-state confidence (MEASURED/NOT_MEASURED/PARTIAL); weights renormalized; gates report NOT_EVALUATED (DEEPTHINK_14) | 01, 06 |
| Debt estimation | `count × constant hours` linear sum; Ratings invents `LOC/100` dev-hours (~50× off 30 min/LOC anchor); ROI fields with no data source | Remediation functions (constant/linear/offset) with pessimism-corrected minutes; batching discount + context cost + rewrite cap; exposure multiplier from graph centrality; churn/age-modulated priority; effort intervals (RESEARCH_04, DEEPTHINK_05/07) | 02 |
| Dependency graph | Three separate full scans per report; `nx.simple_cycles` (exponential risk); length-based cycle severity; O(n) module lookup; no centrality export | One cached `DependencyGraphService`; SCC condensation with reach-based severity and weighted break suggestions; afferent-percentile export feeding Plan 02's Exposure Factor; interface-hash cache (DEEPTHINK_09, RESEARCH_15/02) | 03 |
| SBOM | Direct deps only (transitive hardcoded 0); spec strings as versions; no checksums; **purl normalization backwards** | Full installed closure with resolved versions, RECORD hashes, PEP 639 licenses, CycloneDX 1.5/SPDX relationships, explicit completeness marker | 03 |
| License compliance | Bidirectional substring matching (LGPL→PROHIBITED false positive); no SPDX expressions; cache config unimplemented; no vulnerability/abandonment signal | Exact SPDX-id policy engine with OR/AND expression handling; disk cache; OSV vulnerability lookup over corrected purls; gate feed to Plan 01's license cap (RESEARCH_18) | 03 |
| Quality gate | Absolute project metrics only; unusable on legacy code; dead `small_change_threshold_lines`; silent pass on missing metrics | Two-tier gates (blocking <30 s PR tier, async main tier); differential new-code conditions via AST-stable fingerprints; waterline debt ratchet; hotspot ranking severity×churn×reachability (DEEPTHINK_06/09/02, RESEARCH_15) | 06 |
| Context awareness | Test, generated, and script code rated as production | Shared context classifier; DAMP test profile (CC 25/cognitive 2/clone ×3); generated-code exclusion funnel with SAST retained (DEEPTHINK_12/03) | 04 |
| Presentation & exceptions | Bare letters; unranked issue strings; no suppression or baseline mechanism | Fact-vs-inquiry rendering with confidence; channel presets (ci/pr/ide/dashboard precision tiers); reason-mandatory suppressions with unused-detection; one-way baseline ratchet on AST fingerprints (DEEPTHINK_02/11/14) | 04 |
| Thresholds | Hardcoded constants, identical across 10+ languages, no provenance | Per-language YAML profile plane; local P95 calibrator with clamps; opt-in SZZ/friction rule-validity scoring with LOC+churn controls; PCA weight derivation for Plan 01 (DEEPTHINK_04/10/02, RESEARCH_02/06/09) | 05 |

## Plan index (priority order)

| # | Plan file | Priority | Depends on | Status |
|---|---|---|---|---|
| 01 | `01_Composite_Scoring_Engine.md` | **P0** | — | pre-existing, kept |
| 02 | `02_Technical_Debt_Remediation_Model.md` | **P0** | 03 Phase B (centrality) for its Phase C | pre-existing, kept |
| 03 | `03_Dependency_SBOM_License.md` | **P1** | — (Phase A ships alone) | new |
| 06 | `06_Quality_Gate_Differential.md` | **P1** | 01 (extractors, composite metric), 02 Phase E (delta store), 04 Phase D (fingerprints; interim hash allowed) | new |
| 04 | `04_Ratings_Presentation_Context.md` | **P2** | 01 (models to extend); Phase A (context classifier) is independent and feeds 01/02 denominators — pull it forward | new |
| 05 | `05_Calibration_Empirical_Validity.md` | **P2** | 01 (weight consumption), 02 Phase D (friction collector), 04 (context filter, channels) | new |

**Suggested execution order:** 01-A/B → 02-A/B → 03-A (bug fixes) → 04-A (context classifier) → 06-A (gate honesty) → remaining 01/02 phases → 03-B/C/D → 06-B/C → 05-A/B → 04-B/C/D → 06-D → 05-C/D → 03-E. Rationale: correctness bugs and epistemic-honesty fixes ship first (small, independent, user-visible); cross-plan dependencies (centrality → exposure factor; delta store → differential gate; fingerprints → baseline/gate) then resolve in order.

## Research coverage map

- **Reflected in 01:** DEEPTHINK_01, RESEARCH_01/04/05, DEEPTHINK_14 (partially), RESEARCH_07 (via threshold profiles).
- **Reflected in 02:** RESEARCH_04, DEEPTHINK_05/07/14, RESEARCH_15 (delta aggregation), RESEARCH_01.
- **Reflected in 03:** RESEARCH_18, DEEPTHINK_06/09, RESEARCH_15 (interface hashing), RESEARCH_02 (coupling emphasis).
- **Reflected in 04:** DEEPTHINK_02/03/11/12/14.
- **Reflected in 05:** DEEPTHINK_02/04/10, RESEARCH_02/06/09.
- **Reflected in 06:** DEEPTHINK_02/06/09, RESEARCH_15.
- **Consulted, primarily informing the sibling Quality analyzers rather than Bragi's Ratings/Dependencies planning surface** (their findings enter these plans as inputs/threshold choices): RESEARCH_03 (clone detection algorithms → duplication utility + DEEPTHINK_08/09 choices), RESEARCH_08 (multi-language parity → Plan 05 profile plane), RESEARCH_10/DEEPTHINK_13 (thread-safety scope limits → confidence-weighted severity in 04/05), RESEARCH_11 (type coverage → Plan 01 Comprehensibility metric), RESEARCH_12 (temporal anti-patterns), RESEARCH_13 (documentation empirics → doc-coverage utility, age-decay note), RESEARCH_14 (bug-detection precision → FACT/HEURISTIC classes), RESEARCH_16 (naming quality → naming utility), RESEARCH_17 (error-handling anti-patterns → Reliability inputs).

## Cross-cutting invariants (all plans)

1. **Never reward ignorance**: absence of a measurement is reported, renormalized, or gated — never defaulted to the best grade (DEEPTHINK_14; Plans 01 §3.5, 06 §3.1).
2. **Backward compatibility**: existing public surfaces (`ProjectRatings`, `calculate_from_reports`, `build_asgard_way_gate`, `PackageLicense` booleans, `total_debt_hours`) keep working; new machinery sits behind them. Existing `Asgard_Test/tests_Bragi` suites are the regression contract.
3. **One source of truth per fact**: TDR computed once (02), dependency graph built once (03), report extraction typed once (01), context classified once (04), thresholds resolved once (05).
4. **Deterministic outputs**: same inputs → same scores, profiles, and fingerprints; all caches under `.asgard_cache/` and content/interface-hash keyed.
