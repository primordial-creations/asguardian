# Asgard Uplift — Running Status

**Branch:** `uplift/asgard-p0` | **Started:** 2026-07-17 | **Orchestrator resume point — read this first.**

## Baseline
- 6,611 tests collected in `Asgard_Test/` (run with `python3 -m pytest Asgard_Test/ -q`; no pytest-timeout plugin — do NOT pass `--timeout`).
- All prior `worktree-agent-*` branches are merged into main; no prior uplift work existed.
- Baseline suite status: **NOT GREEN pre-uplift** — 51 failed, 6540 passed, 17 skipped, 3 errors (7m26s). Failure list in `_baseline_failures.txt` (54 entries: 52 tests_Freya, 1 tests_Bragi, 1 tests_Verdandi). Integration bar: no NEW failures vs this baseline; fix pre-existing failures opportunistically within owning slices.

## Backlog (dependency-ordered)

### Wave 0 — Foundations (in progress)
| ID | Slice | Plans | Status |
|---|---|---|---|
| F1 | Heimdall tree-sitter engine, dual-engine decorator, single-parse pipeline | Heimdall/01 | **MERGED** (phases A-B: dual-engine substrate, Python pilot AST rules, [ast] extra, benchmark harness). Agent died at session limit before final report — verified manually (subset green, scope clean). Remaining plan-01 phases unknown; audit before building dependents. |
| F2 | Fingerprint diff gate + structured suppressions + new-code machinery (Heimdall+Bragi shared) | Heimdall/09, Bragi/06 (honesty core) | **MERGED** (b73170d). 84 new tests. Deferred: git-diff engine, hotspot ranker, CLI wiring (`--mode=diff` ready to wire), Plan-02/03 dependent parts, non-Python AST anchoring (snippet-hash fallback in place). |
| F3 | Volundr validation engine + reified suppression schema + GitOps HEAD/default hotfix | Volundr/06 | **MERGED** (52a260c). 70 new tests; tests_Volundr 703 pass. Deferred: generator integration + CLI flags (Phase D → slices 01-05), Terraform plan-JSON ingestion, Validation-Module docs. Note: GitOps `project=default` enforced via validation (VOL-GITOPS-0002), not changed default. |
| F4 | Forseti rule registry/governance + reporting architecture + deprecated!=ERROR fix | Forseti/02, Forseti/08 | **MERGED** (5960a77). 80 new tests; tests_Forseti 1002 pass. Deferred: full non-OpenAPI registry execution (awaits F/01 IR), json_patch auto-fixes, ReceiptReporter, budget_ms enforcement. |

### Wave 1 — P0 capabilities (after the foundation each depends on)
| ID | Slice | Plans | Depends | Status |
|---|---|---|---|---|
| W1-H | Heimdall taint upgrade (Python-first) + security scoring/normalization | H/04, H/06 | F1 partial | not started |
| W1-F | Forseti unified compatibility engine | F/01 | F4 ✓ | **INTERRUPTED at session limit** (resets 5:30pm Brisbane). Partial work preserved as WIP commit 0cce9e4 on branch worktree-agent-af6c2004b36b478eb (new Compatibility/ package, GraphQL/AsyncAPI diff services, CLI handlers — UNTESTED). Resume: relaunch agent in that worktree to finish + test before merging. |
| W1-Fr | Freya unified severity/grade-capping + a11y dual-axis/ARIA | Fr/01, Fr/02 | — | **MERGED** (a05cd59). ~130 new tests; httpx declared. Known pre-existing bug flagged: `_unified_tester_runners.py` attr access masked by exception handler. |
| W1-V | Verdandi stats core (HL/Glass Δ, t-digest, CO) + burn-rate pairing fix + p75 CWV | Ve/03A-C, Ve/02.1-4, Ve/01 | — | **MERGED** (da6f0fb) after adversarial review + fixes. 97 new tests; tests_Verdandi 952 pass. Deferred: CLI wiring for new APIs, Ve/02.5-8, 03D-G. Latent burn-rate scale bug also fixed. |
| W1-Vo-CICD | Volundr zero-trust CI/CD | Vo/04 | F3 ✓ | **MERGED** (219b218). 42 new tests. FLAG: curated SHA pin-map needs release-time verification. Deferred: zizmor self-audit, CICD-Module doc reconciliation. |
| W1-Vo-K8s | Volundr K8s hardening | Vo/01 | F3 ✓ | **MERGED** — NSA/CISA+CIS matrix, suppression presets, engine delegation, CLI flags. Combined Volundr tests 817 pass. |
| W1-B | Bragi composite scoring + debt model core + license/purl/SBOM bug fixes | B/01, B/02, B/03-A | — | **MERGED** after adversarial review (5 BLOCKERs + 6 MAJORs) and fix commit 71eb1f9; license repros re-verified by orchestrator. tests_Bragi 1527 pass (+1 pre-existing java fail). |

### Wave 2 — P1 (plan detail at wave start)
Heimdall hotspots/test-context (H/08); Forseti OpenAPI linting (F/03), lifecycle (F/04), JSON-Schema core (F/05); Freya perf budgets (Fr/03), visual (Fr/04), security framing (Fr/05); Verdandi system/cache/database (Ve/06, 04, 07, 03D-E); Volundr Docker (Vo/03), scoring (Vo/07), GitOps/Kustomize/Helm rest (Vo/05); Bragi SBOM/graph (B/03-B..E), differential gate (B/06 rest).

### Wave 3 — P2/P3
H/02 SOLID CIR, H/03 architecture CSP, H/07 domain scanners, H/05 cohesion, H/10 eval; F/06 contract testing, F/07 cross-format alignment; Fr/06 crawler/config, Fr/07 testing/packaging; Ve/05 network, Ve/08 tracing/APM, Ve/09 Apdex; Vo/02 Terraform; B/04 presentation/context, B/05 calibration. Docs reconciliation continuous.

## Verification contract per slice
1. Full suite green (`python3 -m pytest Asgard_Test/ -q`).
2. Zero-config CLI run on ≥1 non-GAIA reference repo (rotate: Kairos, Talos, GVA, Lexicon, Adrasta — read-only!).
3. GAIA-leak grep audit of default code paths.
4. Scoring/severity/confidence cross-module consistency check.
5. Commit on `uplift/asgard-p0` with clear message; update this file.

## Log
- 2026-07-17: Orientation complete; branch created; planning docs committed. Noted: ASGARD_UPLIFT_GOAL.md/PROMPT.md vanished from disk mid-session (recreated from context); a `Claude Team/.../learnings.md` deletion appeared in git status that this session did not make — another process may be touching the repo.
