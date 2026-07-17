# Asgard Uplift — Goal

## North Star

Asgard (published as `asguardian`) is to become a **rigorous, epistemically honest, general-purpose code-quality and developer-tooling platform** — a self-hostable "SonarQube-and-beyond" that any team can point at any codebase and trust. It unifies static analysis, security scanning, API/schema validation, performance analysis, web/UI testing, dependency auditing, and infrastructure generation behind a single `asgard` CLI, organised into Norse-named sub-tools: **Heimdall** (static analysis / security / quality gates), **Forseti** (API & schema validation), **Freya** (web & UI testing), **Verdandi** (performance & SLO analysis), **Volundr** (infrastructure generation), and **Bragi** (ratings & dependency intelligence).

## The One Non-Negotiable: General-Purpose First

**Asgard is NOT a GAIA-specific tool.** GAIA is one consumer among many. Every capability must be designed to work on *any* codebase, in *any* organisation, with no assumptions about GAIA's structure, naming conventions, infrastructure, or house rules.

Concretely, this means:

- **No hard-coded GAIA assumptions.** Any GAIA-specific rule (e.g. the lazy-imports convention, GAIA path layouts, internal service names) must live behind opt-in configuration, a named profile, or a plugin — never in the default code path.
- **Language-agnostic by architecture.** Detection must run through a canonical, AST-backed intermediate representation (tree-sitter based) so that adding a language is additive, not a rewrite. Python is the reference language; Python-only shortcuts are technical debt.
- **Sensible zero-config defaults.** `asgard <tool> <command> <path>` must produce useful, correct output on a fresh third-party repo with no setup. Configuration deepens behaviour; it is never required to get value.
- **Portable inputs and outputs.** Consume standard formats (OpenAPI, JSON Schema, Avro, SARIF inputs, OTel/metrics JSON, Dockerfiles, Terraform plans, etc.) and emit standard, tool-agnostic formats (SARIF, JUnit, JSON, human-readable) that slot into anyone's CI, IDE, or dashboard.
- **No private infrastructure coupling.** Nothing in the default path may depend on GAIA's Vault, MariaDB, k3s cluster, Gitea, or internal endpoints. Integrations are optional adapters.

If a design decision would make Asgard better for GAIA but worse (or unusable) for an unknown external repo, the external repo wins.

## What "Intended Form" Means

The current implementation has broad surface coverage but shallow, sometimes gameable, and occasionally unsound internals (regex heuristics, arithmetic-mean scoring, per-format checkers, confidently-wrong findings). The intended form is defined in detail across **53 upgrade-plan files in `_Docs/Planning/<Module>/`** (each module has a `00_Overview.md` gap analysis plus P0–P3 themed plans). The uplift must realise those plans. The through-lines are:

1. **Depth over breadth.** AST-accurate detection via tree-sitter instead of regex guessing; inter-procedural taint analysis instead of pattern-matching; structural compatibility engines instead of per-format one-offs.
2. **Statistically principled scoring.** Replace arithmetic means and worst-severity lookups with defensible mathematics — gated/geometric composites, size normalisation, effect-size-gated regression detection, p75 web-vitals bands, correctly-paired multi-window burn rates.
3. **Epistemic honesty.** Findings carry confidence separate from severity; the tool says "needs review" or "insufficient data" rather than bluffing; scores are explainable and resistant to gaming; reports label lab-vs-field, synthetic baselines, and scope.
4. **Developer trust.** Structured suppressions with reasons, baseline ratchets, and diff-based "clean as you code" gating so teams aren't drowned in alert fatigue or blocked by legacy debt.
5. **Secure-by-default generation.** Volundr emits maximally-hardened infrastructure by default; relaxations are explicit, reasoned, and leave machine-readable receipts.

## Reference Repositories (the proving ground)

The general-purpose mandate is validated against six real, independent repositories in `/home/jake/Documents/`. Between them they span Python, JavaScript, TypeScript, Go, and C — so "works on any codebase, in any language" is tested, not asserted. **Crucially, five of the six are NOT GAIA** — they are the primary evidence that Asgard is not GAIA-specific.

| Repo | Path | Character | Primary languages |
|------|------|-----------|-------------------|
| GAIA | `/home/jake/Documents/GAIA/` | Huge polyglot monorepo | JS, Go, TS, Python |
| Lexicon | `/home/jake/Documents/GAIA/Lexicon/` | Polyglot SDK | multi-language |
| Adrasta | `/home/jake/Documents/GAIA/Adrasta/` | Agentic framework | Python |
| Kairos | `/home/jake/Documents/Kairos/` | IDE-like program | JS, TS, C |
| Talos | `/home/jake/Documents/Talos/` | Agent / VM / container orchestration | JS, TS, Python |
| GVA | `/home/jake/Documents/GVA/` | Voice / local assistant | Python, JS, Go |

These repos are **read-only test targets** — Asgard analyses them; it must never modify them. GAIA is included as the large-scale/monorepo stress test, but a capability is only "done" once it also works cleanly on the non-GAIA repos with zero configuration.

## Definition of Done

- Every P0 plan across all six modules is implemented, tested, and verified end-to-end on the **non-GAIA reference repositories** (Kairos, Talos, GVA, Lexicon, Adrasta) — not only on GAIA.
- The full existing test suite (~350+ tests) stays green; new capabilities ship with tests.
- `asgard` runs cleanly against a fresh external codebase with zero configuration and produces correct, honest, actionable output.
- No GAIA-specific assumption exists in any default code path; any such logic is behind opt-in profiles/plugins and documented as such.
- Documentation (`_Docs/Asgard/`, README) reflects the delivered behaviour — no fictional capabilities.
- Scoring, severity, and confidence are consistent and explainable across all ~30 sub-modules.

## Success Test

Hand Asgard to an engineer who has never heard of GAIA, on a random repository in a language Asgard supports — say Kairos or GVA. Within minutes, with no configuration, they get analysis that is **accurate, honest about its uncertainty, and immediately actionable** — and they trust it enough to put it in their CI gate.
