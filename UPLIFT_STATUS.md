# Asgard Uplift — Running Status

**Branch:** `uplift/asgard-p0` | **Started:** 2026-07-17 | **Orchestrator resume point — read this first.**

## Partials completion — Batch 1 (2026-07-18, branch `uplift/asgard-p1`)
Pushed Waves 0-3 to `origin/main` (95d6766; had to purge a live Vault token in CLAUDE.md from all history first — never reached GitHub; CLAUDE.md now gitignored). Deleted 19 fully-delivered plans (see `DELIVERED.md`). Then completed partials via 8 module-scoped agents, all merged onto `uplift/asgard-p1`:
- **Heimdall/10** evaluation & benchmarking harness — built from NOT_STARTED (corpus, dedup, AST-bbox matching, isotonic calibration, Brier gate).
- **Heimdall/02,03,05,06** — CIR extended to 10 languages + OCP type-switch; anemic-domain/infra-leak detectors; cohesion thresholds via profile plane + `explain_class`; SAVD trend metrics.
- **Heimdall/07.5,07.6** — deserialization (AST variable-origin provenance) + auth timing-compare/BOLA. **Adversarial-reviewed: 2 BLOCKERs + 2 MAJORs found (RCE-muting via textual window, sys.argv/open laundering, FP, narrow secret lexicon) and fixed; re-verified by orchestrator.**
- **Forseti/06,07** — stateful mocks, validation-proxy, Arazzo-lite runner; proto/GraphQL/SQL IR adapters, align discover, CLI. (Agent broke worktree isolation — committed to p1 directly; consolidated cleanly.)
- **Freya/04,05,07** — visual fingerprint report display; **route-conditional CSP escalation (fixed the unconditional-Blocker deviation)**; security scope-matrix HTML; 6 module docs.
- **Verdandi/04.4,06,07** — stampede/XFetch analyzer; PSI/CFS/USE↔RED analyzers; query-budget + fingerprint segmentation. (Audit gap-list was partly stale — several items were already done.)
- **Volundr/02,04,05,07** — Terraform `--plan` CLI + for_each/lifecycle; GitLab/Azure hardening+scoring; Helm values.schema.json/hook hygiene; 5 module docs.
- **Bragi/02,04,05** — git-friction/interest + delta-store; scanner context-stamping + TestHealth; PCA weights into scoring + more language profiles.

## Partials completion — Batches 2 & 3 (2026-07-18)
All merged onto `uplift/asgard-p1` (51 commits ahead of main), each security slice adversarially reviewed:
- **Heimdall/07 remaining 7 domains** (TOCTOU, secrets, container/IaC, TLS, supply-chain, sensitive-data, input-validation) → **plan 07 now COMPLETE (12/12 domains)**. Adversarial review caught 3 BLOCKERs + 4 MAJORs (TLS scanner crash on `verify=False`, secrets semantic-context dead-code offset bug, real-key drop near `os.environ`, dev-dep substring misclass, static confidence_bucket, unflagged `ADD http://`, single-hop PII alias) — all fixed + re-verified.
- **Cross-module CLI wiring** — 13 subcommands (Verdandi cache/system/network/db/slo/self-slo, Heimdall explain/calibrate/validate-rules/eval).
- **Heimdall/04 Phase 4 multi-language taint** (JS/TS/Java CST engine + dispatch language-branching). Adversarial review caught 3 BLOCKERs + 1 MAJOR (branch-kill muting real injections, unevaluated array subscripts, dropped multi-arg flows, `escapeHtml` no-op laundering) — all fixed + re-verified by orchestrator.

**ALL partials delivered — including the two formerly scoped-out items (branch `uplift/asgard-p2`):**
- **Bragi SZZ Stage 2** — SZZ bug-inducing-commit tracing (`git blame -w -C`, offline), Negative-Binomial (NB2/IRLS) rule-validity regression controlling for LOC/churn (size-proxy rule → NEUTRAL), exact-Shapley attribution, typed INSUFFICIENT_DATA + small-sample warnings. 17 new tests.
- **Live OSV/NVD lookup** — strictly opt-in (`--online`/`--nvd-fallback`, double-gated; default path makes ZERO network calls, asserted in tests), TTL disk cache, CVSS→severity, false-clean-proof. Adversarial review passed clean on default-leak/SSRF/cache-traversal/gating/key-leak; caught + fixed one false-clean (partial OSV batch response). 33 new tests.

Nothing remains scoped-out. Documented residual LIMITATIONS (not omissions): taint engines intra-procedural (no cross-file summaries for JS/Java), no import/binding resolution for library-sanitizer shadowing (downgraded not full-cleared), Spring `@RequestParam` seeding unwired, SZZ can't filter commits post-dating the bug report (no tracker integration by design).

Manual follow-up for Jake: `_Docs/Planning/Jake-todo.md` (rotate the Vault token that was in CLAUDE.md; optional CI `[ast]`/online wiring + enable GitHub secret scanning). Known residual limitations documented in-code: taint engines intra-procedural (no cross-file summaries for JS/Java), no import/binding resolution for library-sanitizer shadowing (downgraded not full-cleared), Spring `@RequestParam` seeding unwired. Isolation note: 2 of 8 batch-1 agents (Forseti, Freya) escaped worktrees into the main checkout; batch-2/3 agents were explicitly pinned and stayed isolated.

Prior "Still remaining after batch 1" list is now resolved except the scoped-out items above.

## Plan completeness audit (2026-07-18, 6 independent read-only verifier agents)
Answer to "are ALL plans implemented?": **NO.** ~22 of 47 actionable plan files (the 53 files minus 6 overviews) are FULLY implemented; ~24 PARTIAL; 1 NOT_STARTED. **Plan files retained** (not deleted) — each PARTIAL/NOT_STARTED plan still describes unbuilt work and is the resume roadmap.

| Module | FULLY | PARTIAL | NOT_STARTED |
|---|---|---|---|
| Heimdall | 03, 08, 09 | 01 (TS phase C/D — no JS/TS/Java AST migration), 02 (CIR only 4/10 langs), 04 (taint Python-only, no P4 multi-lang), 05 (cohesion — CLI/profile wiring unconfirmed), 06 (no SAVD trend metrics §D), 07 (3/12 domains: SSRF/ReDoS/crypto only) | **10** (evaluation/benchmarking — corpus/calibration/Brier harness entirely absent) |
| Forseti | 01, 02, 03, 04, 05, 08 | 06 (no stateful/proxy mocks, example-first, Arazzo), 07 (no proto/GraphQL/SQL adapters, no `align discover`/CLI) | — |
| Freya | 01, 02, 03, 06 | 04 (fingerprint report display missing), 05 (CSP-route Blocker made UNCONDITIONAL not route-conditional — design deviation; SRI/mixed-content shipped), 07 (6 module-doc stubs never written) | — |
| Verdandi | 01, 03, 08 | 02 (no sla check_fraction; portfolio/dynamic-budget CLI absent), 04 (stampede/XFetch 04.4 entirely missing), 05 (lib complete but ZERO CLI surface), 06 (PSI, CFS-throttle, USE↔RED correlator entirely missing), 07 (query_budget + fingerprint segmentation missing), 09 (self-SLO CLI absent) | — |
| Volundr | 01, 03, 06, 07 | 00/05/06 (5 module docs never written: GitOps/Kustomize/Helm/Validation/Scoring), 02 (`terraform validate --plan` CLI + for_each/lifecycle unwired; plan_reader not consumed), 04 (non-GHA platforms GitLab/Azure not hardened/scored, use legacy scorer), 05 (Helm values.schema.json + hook hygiene missing) | — |
| Bragi | 01, 03, 06 | 02 (Phase D git-friction/interest + Phase E delta-store missing), 04 (scanner context-stamping NOT wired; TestHealth category absent), 05 (PCA weights computed but not wired into scoring; only 5/11 language profiles; SZZ Stage 2 out) | — |

**Cross-cutting gaps:** CLI wiring for many new library APIs is deferred across Verdandi/Volundr/Bragi/Forseti; `_Docs/Asgard/` module-doc reconciliation is incomplete for Volundr (5 docs) and Freya (6 docs). One design deviation to revisit: Freya CSP→Blocker escalation is unconditional rather than route-tag-conditional (over-escalates).


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

### Wave 2x — CLI wiring
**MERGED** — asguardian passthrough (SARIF verified end-to-end), heimdall dispatch/--scoring/--include-test-context/gate --diff --tier, verdandi cwv-assess/burn-rate-policy/cache warmup/pool-signature, volundr score/gitops validate/--digest/--secret-mount/--edge-service, ASGARD_NO_CACHE + heimdall --no-cache. 40 new tests; full suite 8,372 pass.

### Wave 3 — P2/P3 (ALL 8 MERGED — Sonnet subagents)
First attempt died at the Fable 5 limit before writing code; relaunched on Sonnet. Domain scanners got an adversarial review that caught 3 BLOCKERs + 1 MAJOR (real-vulnerability muting: SSRF `.environ`/`.config` laundering, crypto comment/adjacent-call suppression, ReDoS FP on `(a+b)+`) — all fixed before merge.
| Slice | Plans | Status |
|---|---|---|
| Heimdall SOLID CIR + cohesion/coupling | H/02, H/05 | **MERGED** — CIR for 4 langs (py/java/js/ts), true LCOM4; +29 tests. Deferred: go/csharp/ruby/php/rust/cpp CIR, OCP HIGH-confidence type-switch branch. |
| Heimdall architecture CSP | H/03 | **MERGED** — CSP layer inference, drift detection, module SCC, architecture.yml v2 (back-compat); +18 tests. |
| Heimdall domain scanners | H/07 | **MERGED** (3 of 12 domains: ReDoS Glushkov, SSRF slicing, crypto) after adversarial review + fixes; +48 tests. Deferred: 9 remaining domains (start 7.6 auth/access, 7.5 deserialization). |
| Forseti contract testing/mocks + cross-format alignment | F/06, F/07 | **MERGED** — opt-in live validator, semantic mocks, alignment IR/type-matrix; +58 tests. Deferred: stateful mocks, proxy mode, proto/graphql/sql adapters, align/contract CLI. |
| Freya crawler/config/CI + testing/packaging/docs | Fr/06, Fr/07 | **MERGED** — bounded-concurrency crawl, real Config subpackage + CI gate, L0 tests for 4 subpackages, doc/version fix. |
| Verdandi network/tracing/Apdex + SLO 02.5-8 + STL 03F | Ve/05, 08, 09, 02.5-8, 03F | **MERGED** — +138 tests. Deferred: CLI wiring for new strategies/views. |
| Volundr Terraform + plan-JSON validation | Vo/02 | **MERGED** — default-deny TF rules, plan-JSON ingestion, render/validate/score; +26 tests. Deferred: `terraform validate --plan` CLI, for_each/lifecycle emission. |
| Bragi presentation/context + calibration | B/04, B/05 | **MERGED** — shared context classifier (reuses Heimdall), DAMP profile, channel presets, language profile plane, calibrator, PCA weights; +71 tests. Deferred: PCA→scoring hot-path wiring, scanner context-stamping, SZZ Stage 2, calibrate/validate-rules CLI. |

Also fixed: treesitter parser-cache test-isolation leak (`test_parse_source_graceful_when_unavailable`) — was order-failing since the tree-sitter/CIR work cached parsers; commit 16a2112.

### Final gate (all waves + Wave 3, 2026-07-18)
**8,867 passed / 0 failed** excluding the browser-only `tests_Freya/L1_Integration` suite (physically un-runnable headless — needs a live Chromium). The two remaining non-Freya failures from earlier were both fixed this pass: the treesitter parser-cache test-isolation leak (16a2112) and the one genuine pre-existing failure, a `java.xss` detection gap on bare `writer.println(request.getParameter())` (1166114). The tree is now green apart from the browser-gated Freya integration tests. Net from the 6,540-passing pre-uplift baseline: ~+2,300 tests.

### Remaining after Wave 3
- **H/10 evaluation/benchmarking** machinery (formal corpus, calibration, Brier-score CI gate) — the only unstarted P3 plan.
- **Deferred CLI wiring** accumulated across W3 (Forseti align/contract, Verdandi strategies, Volundr `terraform validate --plan`, Bragi calibrate/validate-rules, Heimdall remaining) — a consolidation slice like W2x.
- **Remaining H/07 domains** (9 of 12) and remaining CIR languages.
- Docs reconciliation sweep + global acceptance run across all reference repos.

Remaining after W3: H/10 evaluation/benchmarking machinery, docs reconciliation sweep (`_Docs/Asgard/` + README), global acceptance run on all reference repos.

## Verification contract per slice
1. Full suite green (`python3 -m pytest Asgard_Test/ -q`).
2. Zero-config CLI run on ≥1 non-GAIA reference repo (rotate: Kairos, Talos, GVA, Lexicon, Adrasta — read-only!).
3. GAIA-leak grep audit of default code paths.
4. Scoring/severity/confidence cross-module consistency check.
5. Commit on `uplift/asgard-p0` with clear message; update this file.

## Integrated verification (2026-07-17 evening)
- Wave 2 gate (2026-07-17 ~20:00): **8,332 passed / 50 failed / 3 errors** — failure set exactly the pre-existing Freya-env + Bragi-java set. +1,792 net new passing tests vs pre-uplift baseline.
- FLAKY-SUSPECT: `tests_Heimdall/L0_Mocked/Security/test_cryptographic_validation_service.py::test_detect_static_iv` failed once in one full-suite ordering, passed on rerun and in all subset orderings. Watch; per zero-flakiness policy investigate if it recurs.
- Zero-config CLI on non-GAIA repos: Forseti `openapi validate` on Kairos real spec → actionable rule-id findings, exit 1, SARIF valid (569 results) via `python3 -m Asgard.Forseti`. **GAP:** unified `asguardian` wrapper does not pass through Forseti's new global flags (`--format sarif`, `--profile`) — needs CLI passthrough wiring (Wave 2 item). Heimdall scan of GVA running.

## Log
- 2026-07-17: Orientation complete; branch created; planning docs committed. Noted: ASGARD_UPLIFT_GOAL.md/PROMPT.md vanished from disk mid-session (recreated from context); a `Claude Team/.../learnings.md` deletion appeared in git status that this session did not make — another process may be touching the repo.
