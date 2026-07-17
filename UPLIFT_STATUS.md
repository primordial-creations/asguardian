# Asgard Uplift — Running Status

**Branch:** `uplift/asgard-p0` | **Started:** 2026-07-17 | **Orchestrator resume point — read this first.**

## Baseline
- 6,611 tests collected in `Asgard_Test/` (run with `python3 -m pytest Asgard_Test/ -q`; no pytest-timeout plugin — do NOT pass `--timeout`).
- All prior `worktree-agent-*` branches are merged into main; no prior uplift work existed.
- Baseline suite status: RUNNING (verify green before integrating any slice).

## Backlog (dependency-ordered)

### Wave 0 — Foundations (in progress)
| ID | Slice | Plans | Status |
|---|---|---|---|
| F1 | Heimdall tree-sitter engine, dual-engine decorator, single-parse pipeline | Heimdall/01 | not started |
| F2 | Fingerprint diff gate + structured suppressions + new-code machinery (Heimdall+Bragi shared) | Heimdall/09, Bragi/06 (honesty core) | not started |
| F3 | Volundr validation engine + reified suppression schema | Volundr/06 | not started |
| F4 | Forseti rule registry/governance + reporting architecture | Forseti/02, Forseti/08 | not started |

### Wave 1 — P0 capabilities (after the foundation each depends on)
| ID | Slice | Plans | Depends | Status |
|---|---|---|---|---|
| W1-H | Heimdall taint upgrade (Python-first) + security scoring/normalization | H/04, H/06 | F1 partial | not started |
| W1-F | Forseti unified compatibility engine | F/01 | F4 | not started |
| W1-Fr | Freya unified severity/grade-capping + a11y dual-axis/ARIA | Fr/01, Fr/02 | — | not started |
| W1-V | Verdandi stats core (HL/Glass Δ, t-digest, CO) + burn-rate pairing fix + p75 CWV | Ve/03A-C, Ve/02.1-4, Ve/01 | — | not started |
| W1-Vo | Volundr K8s hardening + zero-trust CI/CD + GitOps HEAD/default fix | Vo/01, Vo/04, Vo/05 hotfix | F3 | not started |
| W1-B | Bragi composite scoring + debt model core + license/purl/SBOM bug fixes | B/01, B/02, B/03-A | — | not started |

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
