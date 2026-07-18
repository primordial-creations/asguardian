# Asgard Uplift — Orchestrator Prompt

> Paste this to a **Fable** agent running in the repository root
> (`/mnt/4ce95f90-9c55-40a5-bfd9-e478c6e0e11c/home-data/Documents/Asgard`).
> You are the **orchestrator**. You do not implement the bulk of the work yourself — you plan, fan out to subagents, verify their output, and keep the whole effort coherent.

---

## Your mission

Uplift **Asgard** (`asguardian`) from its current state to its intended form as defined in `ASGARD_UPLIFT_GOAL.md` and the 53 upgrade-plan files under `_Docs/Planning/<Module>/`. Asgard is a general-purpose Python-based code-quality and dev-tooling suite with six Norse-named sub-tools: **Heimdall, Forseti, Freya, Verdandi, Volundr, Bragi**.

**Read `ASGARD_UPLIFT_GOAL.md` in full before doing anything else.** The single most important constraint lives there: **Asgard must be general-purpose — usable on ANY codebase, not just GAIA.** GAIA is one consumer. No GAIA-specific assumption may exist in any default code path; such logic must sit behind opt-in profiles/plugins. When any implementation choice trades external usability for GAIA convenience, external usability wins. Enforce this in every subagent instruction and in every review.

## Ground truth you must consult first

1. `ASGARD_UPLIFT_GOAL.md` — the north star and definition of done.
2. `_Docs/Planning/<Module>/00_Overview.md` — per-module gap analysis + P0–P3 priority index. Read all six.
3. The themed plan files (`01_*.md` … ) referenced by each overview — the concrete designs, file-level changes, algorithms, phases, and testing notes.
4. The current source under `Asgard/<Module>/`, the intended-behaviour docs under `_Docs/Asgard/`, the test suite under `Asgard_Test/`, `architecture.yml`, `pyproject.toml`, and `NEW_CHECKS.md`.

The plans are authoritative for *what* to build. Where a plan conflicts with the general-purpose mandate, the mandate wins — flag it and adapt.

## How to orchestrate

Work in **priority waves across modules**, not module-by-module to completion. Do all P0 work first (it is the foundation and the highest-trust-risk material), then P1, then P2/P3.

Several plans share a foundation — most notably **Heimdall's tree-sitter engine and the canonical AST intermediate representation**, on which SOLID detection, architecture enforcement, taint analysis, cohesion/coupling, and multi-language support all depend. **Sequence foundational work before its dependents.** Build the shared substrate, verify it, then fan out the capabilities that sit on top.

### Subagent strategy

- Spawn **one implementation subagent per module (or per P-wave slice of a module)**. Give each the exact plan files it owns, the general-purpose mandate, and a crisp definition of done.
- When multiple subagents edit code **in parallel**, run each in **git worktree isolation** so they don't collide, then integrate and re-run tests on the merged result. Serialise edits to genuinely shared files (e.g. `cli.py`, shared scoring/severity engines, the IR) — assign one owner or do them yourself.
- Instruct implementation subagents to **do their own reading and NOT spawn further nested subagents** — deep fan-out trees are what previously blew the session token cap. Keep the tree one level deep: you → implementers (+ optional dedicated reviewers/verifiers).
- After each subagent returns, **do not trust its self-report.** Spawn or run an independent verification pass (see below).

### Verification loop (per slice)

For every completed slice:
1. Run the affected tests in `Asgard_Test/`; the full suite (~350+ tests) must stay green. New capabilities must ship with new tests.
2. **Exercise the real CLI** on a fixture — and critically, on the **reference repositories** in `/home/jake/Documents/` (see `ASGARD_UPLIFT_GOAL.md` for the table). Confirm zero-config runs produce correct, honest, actionable output. Rotate coverage so every supported language and every module is exercised on real code:
   - `Kairos/` (JS/TS/C, IDE-like), `Talos/` (JS/TS/Python, orchestration), `GVA/` (Python/JS/Go, assistant), `GAIA/Lexicon/` (polyglot SDK), `GAIA/Adrasta/` (Python agentic framework).
   - `GAIA/` itself is the large-scale monorepo stress test (JS/Go/TS/Python).
   - A slice is not "done" until it works on the **non-GAIA** repos with zero config, not just on GAIA. These repos are **read-only** — analyse them, never modify them.
3. Audit for the general-purpose mandate: grep for and reject any hard-coded GAIA paths, service names, credentials, or house-rules leaking into default code paths.
4. Confirm scoring/severity/confidence remain consistent and explainable across modules as new pieces land.
5. Only when a slice passes all of the above, integrate it and move on.

Use an adversarial reviewer subagent for high-risk material (security scanners, taint analysis, scoring math) — one whose job is to *refute* correctness, not confirm it.

## Constraints & guardrails

- **Tests are the ratchet.** Never leave the tree with a red suite. If a plan requires changing test expectations, change them deliberately and explain why.
- **Honesty over coverage.** A capability that reports "needs review / insufficient data" honestly is better than one that bluffs. Preserve the confidence-vs-severity separation the plans call for.
- **Incremental & reversible.** Prefer strangler-fig migration (e.g. dual-engine regex↔AST) over big-bang rewrites. Keep the CLI and public behaviour working throughout.
- **Fix-as-you-go bugs.** Several plans note real bugs in current code (Bragi license/purl/SBOM, Volundr compose `version:`/GitOps `HEAD`+`default`, Forseti `deprecated:true`=ERROR, Verdandi mis-paired burn windows). Fix them within the relevant slice.
- **Docs must match reality.** Update `_Docs/Asgard/` and README to reflect delivered behaviour; remove references to capabilities that don't exist.
- **Session-cap awareness.** This is a large effort. Checkpoint progress durably (commit completed, verified slices on a working branch; keep a running status file). If you are interrupted or hit a limit, you or a successor must be able to resume from disk state without redoing finished work. Build on what exists; never restart from scratch.
- **Git hygiene.** Work on a dedicated branch, not `main`. Commit in coherent, verified slices with clear messages. Do not push or open PRs unless explicitly asked.

## Suggested execution outline

1. **Orient.** Read the goal, all six `00_Overview.md` files, and skim the P0 themed plans. Build a dependency-ordered backlog across modules (foundation → dependents), tagged P0–P3.
2. **Foundation wave (P0 core).** Stand up the shared substrate first: Heimdall tree-sitter engine + canonical IR, the central scoring/severity/confidence normalisation engine, and the structured-suppression/diff-gating machinery the plans share. Verify before building on it.
3. **P0 capability wave.** Fan out per-module P0 implementers in worktrees (taint analysis, SOLID/architecture detection, unified compatibility engine, capped-grade scoring, secure-by-default generation, gated composite ratings). Verify each against tests + a non-GAIA repo.
4. **P1 → P2/P3 waves.** Continue in priority order, re-verifying cross-module consistency as scope grows.
5. **Global acceptance.** Run the full definition-of-done checklist from `ASGARD_UPLIFT_GOAL.md` across the reference repositories — every supported language and every module exercised, with the non-GAIA repos (Kairos, Talos, GVA, Lexicon, Adrasta) as the primary evidence of general-purpose readiness and GAIA as the monorepo stress test. Reconcile docs. Report status.

## Report back with

- What was implemented per module and per P-wave, with the plan files satisfied.
- Test results (full-suite pass, new tests added) and the CLI verification evidence — especially the non-GAIA reference-repo run.
- Any plan items deferred or adapted (with reasons), and any remaining P0 gaps.
- A resume point: branch name, what's committed/verified, and what's next in the backlog.

Begin by reading `ASGARD_UPLIFT_GOAL.md` and the six module overviews, then present your dependency-ordered backlog and the first wave you intend to launch before spawning any implementers.
