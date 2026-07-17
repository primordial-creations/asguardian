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
| W1-H | Heimdall taint upgrade (Python-first) + security scoring/normalization | H/04, H/06 | F1 ✓ | **MERGED** (8d509be) after adversarial review (2 BLOCKERs: container laundering, sanitize_* muting; 2 MAJORs: resolved-clean FP, same-line dedup) + fixes. +103 new tests; tests_Heimdall 1539 pass. Deferred: H/04 P4 multi-language CST taint, CLI wiring (dispatch engine, --scoring=v2, confidence buckets in reports), SAVD/Bragi gate feed. |
| W1-Hx | Heimdall general-purpose hygiene: lazy-imports + env-fallbacks behind `--profile gaia`; reports to `.asgard/reports/`; stale artifacts purged | goal doc | — | **MERGED** (bb6bdd8) + verified end-to-end on Adrasta. |
| W1-F | Forseti unified compatibility engine | F/01 | F4 ✓ | **MERGED** — 75 new tests, tests_Forseti 1077 pass. New `forseti compat check` CLI, GraphQL+AsyncAPI diffing, DEEPTHINK_04 scoring w/ blast-radius receipts. Legacy check-compat kept, augmented with score fields. |
| W1-Fr | Freya unified severity/grade-capping + a11y dual-axis/ARIA | Fr/01, Fr/02 | — | **MERGED** (a05cd59). ~130 new tests; httpx declared. Known pre-existing bug flagged: `_unified_tester_runners.py` attr access masked by exception handler. |
| W1-V | Verdandi stats core (HL/Glass Δ, t-digest, CO) + burn-rate pairing fix + p75 CWV | Ve/03A-C, Ve/02.1-4, Ve/01 | — | **MERGED** (da6f0fb) after adversarial review + fixes. 97 new tests; tests_Verdandi 952 pass. Deferred: CLI wiring for new APIs, Ve/02.5-8, 03D-G. Latent burn-rate scale bug also fixed. |
| W1-Vo-CICD | Volundr zero-trust CI/CD | Vo/04 | F3 ✓ | **MERGED** (219b218). 42 new tests. FLAG: curated SHA pin-map needs release-time verification. Deferred: zizmor self-audit, CICD-Module doc reconciliation. |
| W1-Vo-K8s | Volundr K8s hardening | Vo/01 | F3 ✓ | **MERGED** — NSA/CISA+CIS matrix, suppression presets, engine delegation, CLI flags. Combined Volundr tests 817 pass. |
| W1-B | Bragi composite scoring + debt model core + license/purl/SBOM bug fixes | B/01, B/02, B/03-A | — | **MERGED** after adversarial review (5 BLOCKERs + 6 MAJORs) and fix commit 71eb1f9; license repros re-verified by orchestrator. tests_Bragi 1527 pass (+1 pre-existing java fail). |

### Wave 2 — P1 (LAUNCHED — 7 agents in worktrees)
| Slice | Plans | Status |
|---|---|---|
| Heimdall hotspots/test-context | H/08 | **MERGED** — 121 tests; tests_Heimdall 1676 pass. Flags: CLI --include-test-context, PRDecoration + Shared/Issues consumption wiring wanted. |
| Forseti OpenAPI linting + lifecycle | F/03, F/04 | **MERGED** — registry 50→112 rules (OpenAPI 7→69), completeness tiers, OWASP set, SemVer/migration guides; 82 new tests (1159 pass). Deferred: AsyncAPI payload-rule execution, Forseti module docs. |
| Forseti JSON-Schema core (JSONSchema/ dir only) | F/05 | **MERGED** — compiled engine, 2020-12, 283-case suite parity, dialect converter, LLM profiles; tests_Forseti 1514 pass combined. Flags: OpenAPI spec_converter wiring, jsonschema CLI subcommands, llm.* registry registration. |
| Freya perf budgets + visual epistemics + security framing | Fr/03-05 | **MERGED** — 117 new tests (1203 pass ex-L1). Flags: html_reporter epistemic mirrors + CSP/route Blocker escalation deferred to Fr/06 slice; baseline-compare inconclusive = exit 2 (new convention). |
| Verdandi system/cache/database + small-batch/baselines | Ve/06.1-3, 04.1-3, 07.1-2, 03D-E | **MERGED** — 83 new tests (1035 pass); System/Cache/Database docs rewritten to real APIs. Flag: CLI parity for new APIs deferred. |
| Volundr Docker + composite scoring + GitOps/Kustomize/Helm rest | Vo/03, 07, 05 | **MERGED** — 85 new tests (901 pass). Deferred: CLI flags (volundr score etc.), Terraform scorer (Vo/02), Helm chart internals, non-GHA CICD engine scoring. |
| Bragi graph service/SBOM B-E + differential gate remainder | B/03B-E, B/06 rest | **MERGED** — 70 new tests (1597 pass). CAUTION: `.asgard_cache/` writes into scanned path by default (best-effort); use `use_disk_cache=False` or clean up when scanning read-only reference repos. Flags: Heimdall CLI gate flags (--diff/--tier), Plan 02-E debt delta producer. |

Wave 2 leftovers to schedule after: Freya testing/packaging (Fr/07).

**Cross-module CLI wiring slice: MERGED** (this worktree). 40 new CLI tests, zero new failures vs baseline (full suite 8372 pass / 50 fail == baseline minus 1). Delivered: asguardian module-flag passthrough (pre-argparse dispatch; `forseti --format sarif ...` verified valid SARIF on Kairos spec); Heimdall `--scoring {v1,v2}` + LOC-normalized dual scores, security scan routed through DispatchEngine with qualitative confidence buckets + priority ordering, `.heimdall.yml` test_context_enabled/strict_scan_paths + `--include-test-context`, gate `--diff/--base/--tier {pr,main}` -> evaluate_differential; Verdandi `web cwv-assess`, `slo burn-rate-policy`, `cache warmup`, `db pool-signature`; Volundr `score` (grade+remediation, threshold exit), `gitops validate`, docker `--digest/--secret-mount`, compose `--edge-service`; ASGARD_NO_CACHE env + `heimdall scan --no-cache` disable Bragi graph/license disk caches (Adrasta scan verified clean). Freya `--fail-on/--min-grade` confirmed already documented in crawl help.

### Wave 3 — P2/P3
H/02 SOLID CIR, H/03 architecture CSP, H/07 domain scanners, H/05 cohesion, H/10 eval; F/06 contract testing, F/07 cross-format alignment; Fr/06 crawler/config, Fr/07 testing/packaging; Ve/05 network, Ve/08 tracing/APM, Ve/09 Apdex; Vo/02 Terraform; B/04 presentation/context, B/05 calibration. Docs reconciliation continuous.

## Verification contract per slice
1. Full suite green (`python3 -m pytest Asgard_Test/ -q`).
2. Zero-config CLI run on ≥1 non-GAIA reference repo (rotate: Kairos, Talos, GVA, Lexicon, Adrasta — read-only!).
3. GAIA-leak grep audit of default code paths.
4. Scoring/severity/confidence cross-module consistency check.
5. Commit on `uplift/asgard-p0` with clear message; update this file.

## Integrated verification (2026-07-17 evening)
- Full suite on integrated branch: **7,274 passed / 50 failed / 3 errors** — failure set == baseline minus the Verdandi L8 fix. +734 net new passing tests.
- FLAKY-SUSPECT: `tests_Heimdall/L0_Mocked/Security/test_cryptographic_validation_service.py::test_detect_static_iv` failed once in one full-suite ordering, passed on rerun and in all subset orderings. Watch; per zero-flakiness policy investigate if it recurs.
- Zero-config CLI on non-GAIA repos: Forseti `openapi validate` on Kairos real spec → actionable rule-id findings, exit 1, SARIF valid (569 results) via `python3 -m Asgard.Forseti`. **GAP:** unified `asguardian` wrapper does not pass through Forseti's new global flags (`--format sarif`, `--profile`) — needs CLI passthrough wiring (Wave 2 item). Heimdall scan of GVA running.

## Log
- 2026-07-17: Orientation complete; branch created; planning docs committed. Noted: ASGARD_UPLIFT_GOAL.md/PROMPT.md vanished from disk mid-session (recreated from context); a `Claude Team/.../learnings.md` deletion appeared in git status that this session did not make — another process may be touching the repo.
